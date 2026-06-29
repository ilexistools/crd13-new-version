import asyncio

from agents import Agent, ModelSettings, Runner
from agents.mcp import MCPServerStreamableHttp
from pydantic import BaseModel
from app.orchestration.config import default_model, load_environment
from app.orchestration.util import load_agent_config


class GPTAgentResponse(BaseModel):
    final_output: str


class GPTAgent(Agent):

    def __init__(self, **kwargs):
        load_environment()
        self.agent_id = kwargs.get("agent_id", None)
        if self.agent_id is not None:
            config = load_agent_config(self.agent_id, fallback_model=default_model())
            self.name = config["name"]
            self.role = config["role"]
            self.instructions = config["instructions"]
            self.model = config["model"]
            self.max_output_tokens = config["max_tokens"]
            self.output_type = kwargs.get("output_type", GPTAgentResponse)
            self.tools = kwargs.get("tools", [])
            self.handoffs = kwargs.get("handoffs", [])
            self.mcp_url = kwargs.get("mcp_url")
            self.mcp_headers = kwargs.get("mcp_headers", {})
            self.mcp_timeout = kwargs.get("mcp_timeout", 30)
        else:
            self.name = kwargs.get("name", "GPT Agent")
            self.role = kwargs.get("role", "You are a helpful assistant.")
            self.instructions = kwargs.get("instructions", "You are a helpful assistant.")
            self.output_type = kwargs.get("output_type", GPTAgentResponse)
            self.model = kwargs.get("model", default_model())
            self.max_output_tokens = kwargs.get("max_tokens", 2048)
            self.tools = kwargs.get("tools", [])
            self.handoffs = kwargs.get("handoffs", [])
            self.mcp_url = kwargs.get("mcp_url")
            self.mcp_headers = kwargs.get("mcp_headers", {})
            self.mcp_timeout = kwargs.get("mcp_timeout", 30)

        super().__init__(
            name=self.name,
            instructions=self.role + "\n\n" + self.instructions,
            output_type=self.output_type,
            model=self.model,
            tools=self.tools,
            handoffs=self.handoffs,
            mcp_servers=kwargs.get("mcp_servers", []),
            mcp_config=kwargs.get("mcp_config", {}),
            model_settings=ModelSettings(max_tokens=self.max_output_tokens),
        )

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
                return result.final_output

        result = await Runner.run(self, prompt)
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
