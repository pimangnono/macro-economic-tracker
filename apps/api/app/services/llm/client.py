from __future__ import annotations

import logging
from typing import Any

from openai import AsyncOpenAI

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None


def get_openai_client() -> AsyncOpenAI:
    global _client  # noqa: PLW0603
    if _client is not None:
        return _client
    settings = get_settings()
    _client = AsyncOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        max_retries=settings.openai_max_retries,
        timeout=settings.openai_timeout_seconds,
    )
    return _client


async def chat_completion(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 2048,
    response_format: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Send a chat completion request. Returns (content, usage_dict)."""
    settings = get_settings()
    client = get_openai_client()
    resolved_model = model or settings.openai_complex_model

    kwargs: dict[str, Any] = {
        "model": resolved_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format is not None:
        kwargs["response_format"] = response_format

    response = await client.chat.completions.create(**kwargs)
    content = response.choices[0].message.content or ""
    usage: dict[str, Any] = {}
    if response.usage:
        usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
        }
    return content, usage


async def get_embedding(text: str) -> list[float]:
    """Get an embedding vector for the given text."""
    settings = get_settings()
    client = get_openai_client()
    response = await client.embeddings.create(
        model=settings.openai_embedding_model,
        input=text,
        dimensions=settings.openai_embedding_dimensions,
    )
    return response.data[0].embedding
