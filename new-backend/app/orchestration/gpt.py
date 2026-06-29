from pydantic import BaseModel
from openai import AsyncOpenAI, OpenAI

from app.orchestration.config import default_model, load_environment
from app.orchestration.util import load_agent_config


class GPTResponse(BaseModel):
    final_output: str


class GPT:

    def __init__(self, **kwargs):
        load_environment()

        # Clients
        self.client = OpenAI()
        self.async_client = AsyncOpenAI()

        self.agent_id = kwargs.get("agent_id", None)
        if self.agent_id is not None:
            config = load_agent_config(self.agent_id, fallback_model=default_model())
            self.name = config["name"]
            self.role = config["role"]
            self.instructions = config["instructions"]
            self.model = config["model"]
            self.max_output_tokens = config["max_tokens"]
            self.output_type = kwargs.get("output_type", GPTResponse)
        else:
            # Config
            self.name = kwargs.get("name", "GPT Agent")
            self.role = kwargs.get("role", "You are a helpful assistant.")
            self.instructions = kwargs.get("instructions", "You are a helpful assistant.")
            self.output_type = kwargs.get("output_type", GPTResponse)
            self.model = kwargs.get("model", default_model())
            self.max_output_tokens = kwargs.get("max_tokens", 2048)

    async def run(self, prompt: str):
        response = await self.async_client.responses.parse(
            model=self.model,
            input=[
                {"role": "system", "content": self.role + "\n\n" + self.instructions},
                {"role": "user", "content": prompt},
            ],
            max_output_tokens=self.max_output_tokens,
            text_format=self.output_type,
        )
        if response.output_parsed is not None:
            return response.output_parsed
        return self.output_type(final_output=response.output_text)

    def run_sync(self, prompt: str):
        response = self.client.responses.parse(
            model=self.model,
            input=[
                {"role": "system", "content": self.role + "\n\n" + self.instructions},
                {"role": "user", "content": prompt},
            ],
            max_output_tokens=self.max_output_tokens,
            text_format=self.output_type,
        )
        if response.output_parsed is not None:
            return response.output_parsed
        return self.output_type(final_output=response.output_text)
