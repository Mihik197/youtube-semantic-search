from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, Optional, Tuple, Type, TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel

SchemaT = TypeVar("SchemaT", bound=BaseModel)

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


@lru_cache(maxsize=None)
def _client_for_key(api_key: str) -> genai.Client:
    if not api_key:
        raise ValueError("API key required for LLM operations")
    return genai.Client(api_key=api_key)


class LLMService:
    """Tiny helper around the Gemini client for structured JSON responses."""

    def __init__(self, api_key: str, model: str, *, temperature: float = 0.2) -> None:
        if not api_key:
            raise ValueError("API key required for LLM operations")
        self._client = _client_for_key(api_key)
        self.model = model
        self.temperature = temperature

    def count_tokens(self, prompt: str) -> Optional[int]:
        try:
            result = self._client.models.count_tokens(model=self.model, contents=[prompt])
        except Exception:  # pragma: no cover - network failure path
            return None
        return getattr(result, "total_tokens", None)

    def generate_json(
        self,
        prompt: str,
        schema: Type[SchemaT],
        *,
        temperature: Optional[float] = None,
    ) -> Tuple[Any, Optional[SchemaT]]:
        response = self._client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=self.temperature if temperature is None else temperature,
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )
        parsed = getattr(response, "parsed", None)
        if parsed is None and getattr(response, "text", None):
            try:
                parsed = schema.model_validate_json(response.text)
            except Exception:
                parsed = None
        return response, parsed


def summarize_usage(response: Any, prompt_tokens: Optional[int] = None) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """Return (input_tokens, output_tokens, total_tokens) best-effort."""
    usage_in = prompt_tokens
    usage_out = None
    usage_total = None

    usage_meta = getattr(response, "usage_metadata", None)
    if usage_meta:
        usage_in = getattr(usage_meta, "prompt_token_count", usage_in)
        usage_out = getattr(usage_meta, "candidates_token_count", usage_out)
        usage_total = getattr(usage_meta, "total_token_count", usage_total)

    if usage_total is None and usage_in is not None and usage_out is not None:
        usage_total = usage_in + usage_out

    return usage_in, usage_out, usage_total


def log_usage(
    event: str,
    *,
    response: Any = None,
    prompt_tokens: Optional[int] = None,
    logger: Optional[logging.Logger] = None,
    enabled: bool = True,
) -> None:
    """Log token usage for an LLM response when enabled."""

    if not enabled or logger is None:
        return

    usage_in, usage_out, usage_total = summarize_usage(response, prompt_tokens)
    logger.info(
        "%s input_tokens=%s output_tokens=%s total_tokens=%s",
        event,
        usage_in,
        usage_out,
        usage_total,
    )


__all__ = ["LLMService", "summarize_usage", "log_usage"]
