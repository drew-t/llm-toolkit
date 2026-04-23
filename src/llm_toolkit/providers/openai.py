"""OpenAI-compatible provider implementation."""

from __future__ import annotations

import time
from typing import Any

import httpx

from llm_toolkit.providers.base import Response


class OpenAIProvider:
    """Provider for OpenAI-compatible /v1/chat/completions endpoints (vLLM, etc.)."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url

    @staticmethod
    def _parse_response(raw: dict, wall_time: float) -> Response:
        choice = raw.get("choices", [{}])[0]
        usage = raw.get("usage", {})
        return Response(
            text=choice.get("message", {}).get("content", ""),
            prefill_tok_s=0.0,
            decode_tok_s=0.0,
            prompt_tokens=usage.get("prompt_tokens", 0),
            gen_tokens=usage.get("completion_tokens", 0),
            wall_time_s=round(wall_time, 3),
        )

    async def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        timeout: float = 300.0,
        **kwargs: Any,
    ) -> Response:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        async with httpx.AsyncClient(timeout=timeout) as client:
            wall_start = time.perf_counter()
            resp = await client.post(f"{self.base_url}/v1/chat/completions", json=payload)
            wall = time.perf_counter() - wall_start
            resp.raise_for_status()

        return self._parse_response(resp.json(), wall)
