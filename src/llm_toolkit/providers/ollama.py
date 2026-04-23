"""Ollama provider implementation."""

from __future__ import annotations

import time
from typing import Any

import httpx

from llm_toolkit.providers.base import Response

DEFAULT_OLLAMA_URL = "http://localhost:11434"


class OllamaProvider:
    """Provider for Ollama's /api/chat endpoint."""

    def __init__(self, base_url: str = DEFAULT_OLLAMA_URL):
        self.base_url = base_url

    @staticmethod
    def _parse_response(raw: dict, wall_time: float) -> Response:
        ns = 1_000_000_000
        pec = raw.get("prompt_eval_count", 0)
        ped = raw.get("prompt_eval_duration", 0)
        ec = raw.get("eval_count", 0)
        ed = raw.get("eval_duration", 0)

        return Response(
            text=raw.get("message", {}).get("content", ""),
            prefill_tok_s=round(pec / ped * ns if ped else 0, 1),
            decode_tok_s=round(ec / ed * ns if ed else 0, 1),
            prompt_tokens=pec,
            gen_tokens=ec,
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
        num_ctx: int = 8192,
        think: bool = False,
        keep_alive: int = -1,
        **kwargs: Any,
    ) -> Response:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "keep_alive": keep_alive,
            "think": think,
            "options": {
                "num_ctx": num_ctx,
                "num_predict": max_tokens,
                "temperature": temperature,
            },
        }

        async with httpx.AsyncClient(timeout=timeout) as client:
            wall_start = time.perf_counter()
            resp = await client.post(f"{self.base_url}/api/chat", json=payload)
            wall = time.perf_counter() - wall_start
            resp.raise_for_status()

        return self._parse_response(resp.json(), wall)
