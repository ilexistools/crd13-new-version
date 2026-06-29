import asyncio
import sys
from pathlib import Path

from agents import ModelSettings, Runner
from pydantic import BaseModel

from app.orchestration.config import load_environment, sandbox_model
from app.orchestration.util import load_agent_config

from agents.run import RunConfig
from agents.sandbox import SandboxAgent, SandboxRunConfig
from agents.sandbox.capabilities import LocalDirLazySkillSource, Capabilities, Skills
from agents.sandbox.entries import LocalDir
from agents.sandbox.session.sandbox_client import BaseSandboxClient

from agents.mcp import MCPServerStreamableHttp


def _create_sandbox_client() -> BaseSandboxClient:
    if sys.platform != "win32":
        from agents.sandbox.sandboxes.unix_local import UnixLocalSandboxClient
        return UnixLocalSandboxClient()
    try:
        from agents.sandbox.sandboxes.docker import DockerSandboxClient
        return DockerSandboxClient()
    except ImportError as e:
        raise ImportError(
            "No sandbox backend available on Windows. "
            "Install the 'docker' extra or run on a Unix system."
        ) from e


class GPTAgentResponse(BaseModel):
    final_output: str


DEFAULT_SKILLS_DIR = Path(__file__).resolve().parents[1] / "assets" / "skills"


def resolve_skills_dir(skills_dir: str | Path) -> Path:
    path = Path(skills_dir)
    if path.exists() or path.is_absolute():
        return path

    app_relative_path = Path(__file__).resolve().parents[1] / path
    if app_relative_path.exists():
        return app_relative_path

    return path


class GPTSandboxAgent(SandboxAgent):

    def __init__(self, **kwargs):
        load_environment()
        self.sandbox_client = kwargs.get("sandbox_client", None)
        self.agent_id = kwargs.get("agent_id", None)
        if self.agent_id is not None:
            config = load_agent_config(self.agent_id, fallback_model=sandbox_model())
            self.name = config["name"]
            self.role = config["role"]
            self.instructions = config["instructions"]
            self.model = config["model"]
            self.max_output_tokens = config["max_tokens"]
            self.output_type = kwargs.get("output_type", GPTAgentResponse)
            self.tools = kwargs.get("tools", [])
            self.handoffs = kwargs.get("handoffs", [])
            self.skills_dir = resolve_skills_dir(kwargs.get("skills_dir", DEFAULT_SKILLS_DIR))
            self.mcp_url = kwargs.get("mcp_url")
            self.mcp_headers = kwargs.get("mcp_headers", {})
            self.mcp_timeout = kwargs.get("mcp_timeout", 30)
            agent_instructions = self.role + "\n\n" + self.instructions
        else:
            role_provided = "role" in kwargs
            self.name = kwargs.get("name", "GPT Sandbox Agent")
            self.role = kwargs.get("role", "You are a helpful assistant.")
            self.instructions = kwargs.get("instructions", "You are a helpful assistant.")
            self.output_type = kwargs.get("output_type", GPTAgentResponse)
            self.model = kwargs.get("model", sandbox_model())
            self.max_output_tokens = kwargs.get("max_tokens", 2048)
            self.tools = kwargs.get("tools", [])
            self.handoffs = kwargs.get("handoffs", [])
            self.skills_dir = resolve_skills_dir(kwargs.get("skills_dir", DEFAULT_SKILLS_DIR))
            self.mcp_url = kwargs.get("mcp_url")
            self.mcp_headers = kwargs.get("mcp_headers", {})
            self.mcp_timeout = kwargs.get("mcp_timeout", 30)

            if callable(self.instructions) or self.instructions is None:
                agent_instructions = self.instructions
            elif role_provided:
                agent_instructions = self.role + "\n\n" + self.instructions
            else:
                agent_instructions = self.instructions

        capabilities = kwargs.get(
            "capabilities",
            Capabilities.default() + [
                Skills(
                    lazy_from=LocalDirLazySkillSource(
                        source=LocalDir(src=self.skills_dir),
                    ),
                    skills_path=".agents",
                ),
            ],
        )

        super().__init__(
            name=self.name,
            handoff_description=kwargs.get("handoff_description"),
            tools=self.tools,
            mcp_servers=kwargs.get("mcp_servers", []),
            mcp_config=kwargs.get("mcp_config", {}),
            instructions=agent_instructions,
            prompt=kwargs.get("prompt"),
            handoffs=self.handoffs,
            output_type=self.output_type,
            model=self.model,
            model_settings=kwargs.get(
                "model_settings",
                ModelSettings(max_tokens=self.max_output_tokens),
            ),
            input_guardrails=kwargs.get("input_guardrails", []),
            output_guardrails=kwargs.get("output_guardrails", []),
            hooks=kwargs.get("hooks"),
            tool_use_behavior=kwargs.get("tool_use_behavior", "run_llm_again"),
            reset_tool_choice=kwargs.get("reset_tool_choice", True),
            default_manifest=kwargs.get("default_manifest"),
            base_instructions=kwargs.get("base_instructions"),
            capabilities=capabilities,
            run_as=kwargs.get("run_as"),
        )

    async def run(self, prompt: str):
        client = self.sandbox_client or _create_sandbox_client()
        sandbox_run_config = RunConfig(
            sandbox=SandboxRunConfig(client=client),
        )

        if self.mcp_url:
            async with MCPServerStreamableHttp(
                name="mcp_server",
                params={
                    "url": self.mcp_url,
                    "headers": self.mcp_headers,
                    "timeout": self.mcp_timeout,
                },
                cache_tools_list=True,
                max_retry_attempts=3,
            ) as mcp_server:
                self.mcp_servers = [mcp_server]
                result = await Runner.run(self, prompt, run_config=sandbox_run_config)
                return result.final_output

        result = await Runner.run(self, prompt, run_config=sandbox_run_config)
        return result.final_output

    def run_sync(self, prompt: str):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.run(prompt))

        raise RuntimeError(
            "run_sync() cannot be used inside an active event loop. "
            "Use `await run(prompt)` in async endpoints."
        )
