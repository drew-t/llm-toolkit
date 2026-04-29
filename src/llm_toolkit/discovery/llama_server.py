"""llama.cpp llama-server adapter."""

from __future__ import annotations

import httpx

from llm_toolkit.discovery.types import LoadedModel, ModelInfo, RunnerSnapshot

TIMEOUT_S = 3.0


class LlamaServerAdapter:
    name = "llama-server"

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
                r = await client.get("/props")
                r.raise_for_status()
                props = r.json()
                version = props.get("build_info")
                gen_settings = props.get("default_generation_settings", {})
                if "n_ctx" in gen_settings:
                    raw["n_ctx"] = gen_settings["n_ctx"]
                if "system_info" in props:
                    raw["system_info"] = props["system_info"]
                reachable = True
            except Exception as e:
                return RunnerSnapshot(
                    runner=self.name, base_url=base_url, gpu=gpu, version=None,
                    reachable=False, error=f"props: {e!r}",
                )

            try:
                r = await client.get("/v1/models")
                r.raise_for_status()
                for m in r.json().get("data", []):
                    installed.append(ModelInfo(tag=m.get("id", "")))
            except Exception as e:
                error = f"models: {e!r}"

            try:
                r = await client.get("/slots")
                if r.status_code == 200:
                    raw["slots"] = r.json()
            except Exception:
                pass

        loaded = [LoadedModel(tag=m.tag) for m in installed]

        return RunnerSnapshot(
            runner=self.name, base_url=base_url, gpu=gpu, version=version,
            reachable=reachable, error=error,
            installed_models=installed, loaded_models=loaded,
            raw=raw,
        )
