"""vLLM runner adapter."""

from __future__ import annotations

import re

import httpx

from llm_toolkit.discovery.types import LoadedModel, ModelInfo, RunnerSnapshot

TIMEOUT_S = 3.0
_KV_RE = re.compile(r"^vllm:gpu_cache_usage_perc\{[^}]*\}\s+([\d.eE+-]+)", re.MULTILINE)


class VLLMAdapter:
    name = "vllm"

    def __init__(self, *, transport: httpx.BaseTransport | None = None):
        self._transport = transport

    async def probe(self, base_url: str, gpu: str | None = None) -> RunnerSnapshot:
        installed: list[ModelInfo] = []
        version: str | None = None
        raw: dict = {}
        error: str | None = None
        reachable = False

        async with httpx.AsyncClient(
            base_url=base_url, timeout=TIMEOUT_S, transport=self._transport
        ) as client:
            try:
                r = await client.get("/version")
                r.raise_for_status()
                version = r.text.strip().split()[-1] or None
                reachable = True
            except Exception as e:
                return RunnerSnapshot(
                    runner=self.name, base_url=base_url, gpu=gpu, version=None,
                    reachable=False, error=f"version: {e!r}",
                )

            try:
                r = await client.get("/v1/models")
                r.raise_for_status()
                for m in r.json().get("data", []):
                    installed.append(ModelInfo(tag=m.get("id", "")))
            except Exception as e:
                error = f"models: {e!r}"

            try:
                r = await client.get("/metrics")
                if r.status_code == 200:
                    match = _KV_RE.search(r.text)
                    if match:
                        raw["gpu_cache_usage_perc"] = float(match.group(1))
            except Exception:
                # /metrics is optional; ignore failures silently
                pass

        # vLLM serves a single model per process — installed == loaded
        loaded = [LoadedModel(tag=m.tag) for m in installed]

        return RunnerSnapshot(
            runner=self.name, base_url=base_url, gpu=gpu, version=version,
            reachable=reachable, error=error,
            installed_models=installed, loaded_models=loaded,
            raw=raw,
        )
