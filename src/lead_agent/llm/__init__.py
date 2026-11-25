"""Structured-output LLM clients. Claude via the Anthropic SDK, or any OpenAI-compatible
server (Ollama locally, OpenAI, LM Studio, vLLM)."""

from __future__ import annotations

import os

from .anthropic_llm import AnthropicLLM
from .base import LLM, LLMError
from .openai_compat import OpenAICompatibleLLM

__all__ = ["LLM", "AnthropicLLM", "LLMError", "OpenAICompatibleLLM", "select_llm"]


def select_llm(provider: str | None = None) -> LLM:
    """LEAD_AGENT_PROVIDER=anthropic | openai-compatible | auto (default).
    Auto: Claude when ANTHROPIC_API_KEY is set, otherwise the OpenAI-compatible endpoint
    (Ollama at localhost:11434 by default)."""
    provider = provider or os.getenv("LEAD_AGENT_PROVIDER", "auto")
    if provider == "anthropic" or (provider == "auto" and os.getenv("ANTHROPIC_API_KEY")):
        return AnthropicLLM(model=os.getenv("LEAD_AGENT_MODEL", "claude-opus-5-5"))
    return OpenAICompatibleLLM(
        base_url=os.getenv("OPENAI_BASE_URL", "http://localhost:11434/v1"),
        model=os.getenv("LEAD_AGENT_MODEL", "qwen2.5:7b"),
        api_key=os.getenv("OPENAI_API_KEY"),
    )
