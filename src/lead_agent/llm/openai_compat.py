from __future__ import annotations

import json

import httpx
from pydantic import ValidationError

from .base import LLMError, T


class OpenAICompatibleLLM:
    """Any OpenAI-compatible chat completions endpoint. Asks for JSON that matches the schema,
    validates it with Pydantic and retries once with the validation error if it does not."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434/v1",
        model: str = "qwen2.5:7b",
        api_key: str | None = None,
        client: httpx.Client | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self.client = client or httpx.Client(timeout=180, headers=headers)

    def _call(self, messages: list[dict], schema: type[T]) -> str:
        try:
            response = self.client.post(
                f"{self.base_url}/chat/completions",
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0.1,
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": {"name": schema.__name__, "schema": schema.model_json_schema()},
                    },
                },
            )
        except httpx.HTTPError as e:
            raise LLMError(f"Model server not reachable at {self.base_url}: {e}") from e
        if response.status_code >= 400:
            raise LLMError(f"Model server error {response.status_code}: {response.text[:300]}")
        return response.json()["choices"][0]["message"]["content"] or ""

    def structured(self, system: str, user: str, schema: type[T]) -> T:
        schema_hint = json.dumps(schema.model_json_schema())
        messages = [
            {
                "role": "system",
                "content": f"{system}\n\nAnswer with JSON only, matching this JSON schema:\n{schema_hint}",
            },
            {"role": "user", "content": user},
        ]
        content = self._call(messages, schema)
        try:
            return schema.model_validate_json(_strip_fences(content))
        except ValidationError as error:
            messages += [
                {"role": "assistant", "content": content},
                {
                    "role": "user",
                    "content": f"That JSON is invalid: {error.errors()[:3]}. Reply again with valid JSON only.",
                },
            ]
            content = self._call(messages, schema)
            try:
                return schema.model_validate_json(_strip_fences(content))
            except ValidationError as e:
                raise LLMError(f"Model did not return valid {schema.__name__} JSON") from e


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("```", 1)[0]
    return text.strip()
