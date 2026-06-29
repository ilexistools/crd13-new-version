import os

from openai import AsyncOpenAI, OpenAI
from pydantic import BaseModel

from app.orchestration.config import load_environment
from app.orchestration.util import load_agent_config


class GPTLocalResponse(BaseModel):
    final_output: str


def _local_base_url() -> str:
    return os.getenv("LOCAL_BASE_URL", "http://localhost:1234/v1")


def _local_api_key() -> str:
    return os.getenv("LOCAL_API_KEY", "lm-studio")


def _local_model() -> str:
    return os.getenv("LOCAL_MODEL_NAME", "local-model")


class GPTLocal:

    def __init__(self, **kwargs):
        load_environment()

        base_url = kwargs.get("base_url", _local_base_url())
        api_key = kwargs.get("api_key", _local_api_key())

        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.async_client = AsyncOpenAI(base_url=base_url, api_key=api_key)

        self.agent_id = kwargs.get("agent_id", None)
        if self.agent_id is not None:
            config = load_agent_config(self.agent_id, fallback_model=_local_model())
            self.name = config["name"]
            self.role = config["role"]
            self.instructions = config["instructions"]
            self.model = config["model"] or _local_model()
            self.max_output_tokens = config["max_tokens"]
            self.output_type = kwargs.get("output_type", GPTLocalResponse)
        else:
            self.name = kwargs.get("name", "GPT Local")
            self.role = kwargs.get("role", "You are a helpful assistant.")
            self.instructions = kwargs.get("instructions", "You are a helpful assistant.")
            self.output_type = kwargs.get("output_type", GPTLocalResponse)
            self.model = kwargs.get("model", _local_model())
            self.max_output_tokens = kwargs.get("max_tokens", 2048)

    def _build_messages(self, prompt: str) -> list:
        system = self.role + "\n\n" + self.instructions
        is_structured = (
            isinstance(self.output_type, type)
            and issubclass(self.output_type, BaseModel)
            and self.output_type is not GPTLocalResponse
        )
        if is_structured:
            schema = self.output_type.model_json_schema()
            system += f"\n\nRespond only with valid JSON matching this schema:\n{schema}"
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]

    def _parse_response(self, content: str):
        # strip markdown code fences that some local models add
        text = content.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
            text = "\n".join(lines[1:end])
        try:
            return self.output_type.model_validate_json(text)
        except Exception:
            try:
                return self.output_type(final_output=content)
            except Exception:
                return GPTLocalResponse(final_output=content)

    async def run(self, prompt: str):
        response = await self.async_client.chat.completions.create(
            model=self.model,
            messages=self._build_messages(prompt),
            max_tokens=self.max_output_tokens,
        )
        return self._parse_response(response.choices[0].message.content or "")

    def run_sync(self, prompt: str):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=self._build_messages(prompt),
            max_tokens=self.max_output_tokens,
        )
        return self._parse_response(response.choices[0].message.content or "")
