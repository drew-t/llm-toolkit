"""Tests for LlamaServerAdapter."""

from __future__ import annotations

import httpx
import pytest

from llm_toolkit.discovery.llama_server import LlamaServerAdapter


def _t(handler):
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_llama_server_happy_path():
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/props":
            return httpx.Response(200, json={
                "build_info": "build 4500 (abcdef0)",
                "default_generation_settings": {"n_ctx": 8192},
                "system_info": {"CUDA0": "NVIDIA GeForce RTX 3080 Ti, 12288 MiB"},
            })
        if req.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "tmnt-7b-q5"}]})
        if req.url.path == "/slots":
            return httpx.Response(200, json=[{"id": 0, "is_processing": True}])
        return httpx.Response(404)

    snap = await LlamaServerAdapter(transport=_t(handler)).probe("http://x:8080", gpu="3080ti")
    assert snap.reachable is True
    assert snap.version == "build 4500 (abcdef0)"
    assert [m.tag for m in snap.installed_models] == ["tmnt-7b-q5"]
    assert snap.loaded_models[0].tag == "tmnt-7b-q5"
    assert snap.raw["n_ctx"] == 8192
    assert snap.raw["slots"][0]["is_processing"] is True
    assert "CUDA0" in snap.raw["system_info"]


@pytest.mark.asyncio
async def test_llama_server_unreachable():
    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    snap = await LlamaServerAdapter(transport=_t(handler)).probe("http://nope:8080")
    assert snap.reachable is False
    assert snap.error is not None
