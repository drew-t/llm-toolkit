"""Ollama runner adapter."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from llm_toolkit.discovery.types import LoadedModel, ModelInfo, RunnerSnapshot

TIMEOUT_S = 3.0


def _to_epoch(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


class OllamaAdapter:
    name = "ollama"

    def __init__(self, *, transport: httpx.BaseTransport | None = None):
        self._transport = transport

    async def probe(self, base_url: str, gpu: str | None = None) -> RunnerSnapshot:
        installed: list[ModelInfo] = []
        loaded: list[LoadedModel] = []
        version: str | None = None
        error: str | None = None
        reachable = False

        async with httpx.AsyncClient(
            base_url=base_url, timeout=TIMEOUT_S, transport=self._transport
        ) as client:
            try:
                r = await client.get("/api/version")
                r.raise_for_status()
                version = r.json().get("version")
                reachable = True
            except Exception as e:
                return RunnerSnapshot(
                    runner=self.name, base_url=base_url, gpu=gpu, version=None,
                    reachable=False, error=f"version: {e!r}",
                )

            try:
                r = await client.get("/api/tags")
                r.raise_for_status()
                for m in r.json().get("models", []):
                    installed.append(ModelInfo(
                        tag=m.get("name", ""),
                        size_bytes=m.get("size"),
                        modified=_to_epoch(m.get("modified_at")),
                    ))
            except Exception as e:
                error = f"tags: {e!r}"

            try:
                r = await client.get("/api/ps")
                r.raise_for_status()
                for m in r.json().get("models", []):
                    loaded.append(LoadedModel(
                        tag=m.get("name", ""),
                        vram_bytes=m.get("size_vram"),
                        expires_at=_to_epoch(m.get("expires_at")),
                    ))
            except Exception as e:
                error = f"{error}; ps: {e!r}" if error else f"ps: {e!r}"

        return RunnerSnapshot(
            runner=self.name, base_url=base_url, gpu=gpu, version=version,
            reachable=reachable, error=error,
            installed_models=installed, loaded_models=loaded,
            raw={},
        )
