"""Tests for VLLMAdapter."""

from __future__ import annotations

import httpx
import pytest

from llm_toolkit.discovery.vllm import VLLMAdapter


def _t(handler):
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_vllm_happy_path():
    metrics_text = (
        "# HELP vllm:gpu_cache_usage_perc GPU KV cache utilization\n"
        "# TYPE vllm:gpu_cache_usage_perc gauge\n"
        'vllm:gpu_cache_usage_perc{model_name="Qwen/Qwen3-8B"} 0.42\n'
    )

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/version":
            return httpx.Response(200, text="0.6.4")
        if req.url.path == "/v1/models":
            return httpx.Response(200, json={
                "data": [{"id": "Qwen/Qwen3-8B", "object": "model"}]
            })
        if req.url.path == "/metrics":
            return httpx.Response(200, text=metrics_text)
        return httpx.Response(404)

    snap = await VLLMAdapter(transport=_t(handler)).probe("http://x:8000", gpu="3080ti")
    assert snap.reachable is True
    assert snap.version == "0.6.4"
    assert [m.tag for m in snap.installed_models] == ["Qwen/Qwen3-8B"]
    assert [m.tag for m in snap.loaded_models] == ["Qwen/Qwen3-8B"]
    assert snap.raw["gpu_cache_usage_perc"] == 0.42


@pytest.mark.asyncio
async def test_vllm_metrics_optional():
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/version":
            return httpx.Response(200, text="0.6.4")
        if req.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "m"}]})
        return httpx.Response(404)  # /metrics absent

    snap = await VLLMAdapter(transport=_t(handler)).probe("http://x:8000")
    assert snap.reachable is True
    assert "gpu_cache_usage_perc" not in snap.raw  # absence is fine


@pytest.mark.asyncio
async def test_vllm_unreachable():
    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    snap = await VLLMAdapter(transport=_t(handler)).probe("http://nope:8000")
    assert snap.reachable is False
    assert snap.error is not None
