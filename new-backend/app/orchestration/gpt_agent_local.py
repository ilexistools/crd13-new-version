import asyncio
import json
import os
from typing import Any

from openai import AsyncOpenAI
from agents import (
    Agent,
    ModelSettings,
    Runner,
    OpenAIChatCompletionsModel,
    set_tracing_disabled,
)
from agents.mcp import MCPServerStreamableHttp
from pydantic import BaseModel

from app.orchestration.config import load_environment
from app.orchestration.util import load_agent_config


class GPTAgentLocalResponse(BaseModel):
    final_output: str


def _local_base_url() -> str:
    return os.getenv("LOCAL_BASE_URL", "http://localhost:1234/v1")


def _local_api_key() -> str:
    return os.getenv("LOCAL_API_KEY", "lm-studio")


def _local_model() -> str:
    return os.getenv("LOCAL_MODEL_NAME", "local-model")


def _local_disable_tracing() -> bool:
    return os.getenv("LOCAL_DISABLE_TRACING", "true").lower() not in {"0", "false", "no"}


class GPTLocalAgent(Agent):

    def __init__(self, **kwargs):
        load_environment()

        base_url = kwargs.get("base_url", _local_base_url())
        api_key = kwargs.get("api_key", _local_api_key())
        openai_client = AsyncOpenAI(base_url=base_url, api_key=api_key)
        set_tracing_disabled(kwargs.get("disable_tracing", _local_disable_tracing()))

        self.agent_id = kwargs.get("agent_id", None)
        if self.agent_id is not None:
            config = load_agent_config(self.agent_id, fallback_model=_local_model())
            self.name = config["name"]
            self.role = config["role"]
            instructions_text = config["instructions"]
            model_name = config["model"] or _local_model()
            self.max_output_tokens = config["max_tokens"]
            self.requested_output_type = kwargs.get("output_type", GPTAgentLocalResponse)
            self.tools = kwargs.get("tools", [])
            self.handoffs = kwargs.get("handoffs", [])
            self.mcp_url = kwargs.get("mcp_url")
            self.mcp_headers = kwargs.get("mcp_headers", {})
            self.mcp_timeout = kwargs.get("mcp_timeout", 30)
        else:
            self.name = kwargs.get("name", "GPT Local Agent")
            self.role = kwargs.get("role", "You are a helpful assistant.")
            instructions_text = kwargs.get("instructions", "You are a helpful assistant.")
            self.requested_output_type = kwargs.get("output_type", GPTAgentLocalResponse)
            model_name = kwargs.get("model", _local_model())
            self.max_output_tokens = kwargs.get("max_tokens", 2048)
            self.tools = kwargs.get("tools", [])
            self.handoffs = kwargs.get("handoffs", [])
            self.mcp_url = kwargs.get("mcp_url")
            self.mcp_headers = kwargs.get("mcp_headers", {})
            self.mcp_timeout = kwargs.get("mcp_timeout", 30)

        model_obj = OpenAIChatCompletionsModel(
            model=model_name,
            openai_client=openai_client,
        )
        instructions = self.role + "\n\n" + instructions_text
        agent_output_type = self.requested_output_type
        if self._uses_soft_structured_output():
            agent_output_type = str
            schema = json.dumps(self.requested_output_type.model_json_schema(), ensure_ascii=False)
            instructions += (
                "\n\nRespond only with valid JSON matching this schema. "
                "Do not include Markdown code fences or explanatory text.\n"
                f"{schema}"
            )

        super().__init__(
            name=self.name,
            instructions=instructions,
            output_type=agent_output_type,
            model=model_obj,
            tools=self.tools,
            handoffs=self.handoffs,
            mcp_servers=kwargs.get("mcp_servers", []),
            mcp_config=kwargs.get("mcp_config", {}),
            model_settings=ModelSettings(max_tokens=self.max_output_tokens),
        )

    def _uses_soft_structured_output(self) -> bool:
        return (
            isinstance(self.requested_output_type, type)
            and issubclass(self.requested_output_type, BaseModel)
        )

    def _parse_final_output(self, final_output: Any):
        if not self._uses_soft_structured_output():
            return final_output

        if isinstance(final_output, self.requested_output_type):
            return final_output

        text = str(final_output).strip()
        if text.startswith("```"):
            lines = text.splitlines()
            start = 1
            end = len(lines) - 1 if lines and lines[-1].strip() == "```" else len(lines)
            text = "\n".join(lines[start:end]).strip()

        try:
            return self.requested_output_type.model_validate_json(text)
        except Exception:
            if self.requested_output_type is GPTAgentLocalResponse:
                return GPTAgentLocalResponse(final_output=str(final_output))
            raise

    async def run(self, prompt: str):
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
                result = await Runner.run(self, prompt)
                return self._parse_final_output(result.final_output)

        result = await Runner.run(self, prompt)
        return self._parse_final_output(result.final_output)

    def run_sync(self, prompt: str):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.run(prompt))

        raise RuntimeError(
            "run_sync() cannot be used inside an active event loop. "
            "Use `await run(prompt)` in async endpoints."
        )
