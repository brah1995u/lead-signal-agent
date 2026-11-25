from __future__ import annotations

import anthropic

from .base import LLMError, T


class AnthropicLLM:
    """Claude with structured outputs: the response is constrained to the Pydantic schema
    and validated by the SDK (`messages.parse`)."""

    def __init__(self, model: str = "claude-opus-5-5", client: anthropic.Anthropic | None = None):
        self.model = model
        self.client = client or anthropic.Anthropic()

    def structured(self, system: str, user: str, schema: type[T]) -> T:
        try:
            response = self.client.messages.parse(
                model=self.model,
                max_tokens=16000,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_format=schema,
            )
        except anthropic.AuthenticationError as e:
            raise LLMError("Invalid Anthropic API key") from e
        except anthropic.RateLimitError as e:
            raise LLMError("Rate limited by the Anthropic API") from e
        except anthropic.APIError as e:
            raise LLMError(f"Anthropic API error: {e}") from e
        if response.stop_reason == "refusal" or response.parsed_output is None:
            raise LLMError(f"No structured output (stop_reason={response.stop_reason})")
        return response.parsed_output
