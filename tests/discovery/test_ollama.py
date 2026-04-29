"""Tests for OllamaAdapter."""

from __future__ import annotations

import httpx
import pytest

from llm_toolkit.discovery.ollama import OllamaAdapter


def _mock_transport(handler):
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_ollama_happy_path():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.5.7"})
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={
                "models": [
                    {"name": "qwen3:8b", "size": 5_000_000_000,
                     "modified_at": "2026-04-01T00:00:00Z"},
                    {"name": "llama3:8b", "size": 4_000_000_000,
                     "modified_at": "2026-03-15T00:00:00Z"},
                ]
            })
        if request.url.path == "/api/ps":
            return httpx.Response(200, json={
                "models": [
                    {"name": "qwen3:8b", "size_vram": 8_000_000_000,
                     "expires_at": "2026-04-28T16:00:00Z"},
                ]
            })
        return httpx.Response(404)

    adapter = OllamaAdapter(transport=_mock_transport(handler))
    snap = await adapter.probe("http://drubuntu:11434", gpu="3080ti")

    assert snap.runner == "ollama"
    assert snap.reachable is True
    assert snap.error is None
    assert snap.version == "0.5.7"
    assert snap.gpu == "3080ti"
    assert {m.tag for m in snap.installed_models} == {"qwen3:8b", "llama3:8b"}
    assert snap.installed_models[0].size_bytes in {5_000_000_000, 4_000_000_000}
    assert len(snap.loaded_models) == 1
    assert snap.loaded_models[0].tag == "qwen3:8b"
    assert snap.loaded_models[0].vram_bytes == 8_000_000_000


@pytest.mark.asyncio
async def test_ollama_unreachable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    adapter = OllamaAdapter(transport=_mock_transport(handler))
    snap = await adapter.probe("http://nope:11434", gpu=None)

    assert snap.reachable is False
    assert snap.error is not None
    assert snap.installed_models == []
    assert snap.loaded_models == []


@pytest.mark.asyncio
async def test_ollama_partial_only_version():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.5.7"})
        return httpx.Response(500, text="boom")

    adapter = OllamaAdapter(transport=_mock_transport(handler))
    snap = await adapter.probe("http://x:11434", gpu="3080ti")

    assert snap.reachable is True  # /version worked
    assert snap.version == "0.5.7"
    assert snap.installed_models == []
    assert snap.loaded_models == []
    assert snap.error is not None  # captured the failure
