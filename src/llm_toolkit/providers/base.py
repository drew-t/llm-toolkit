"""Provider protocol and Response dataclass."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass
class Response:
    """Standardized response from any LLM provider."""

    text: str
    prefill_tok_s: float
    decode_tok_s: float
    prompt_tokens: int
    gen_tokens: int
    wall_time_s: float


@runtime_checkable
class Provider(Protocol):
    """Protocol for LLM provider backends."""

    async def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        timeout: float = 300.0,
        **kwargs: Any,
    ) -> Response: ...
