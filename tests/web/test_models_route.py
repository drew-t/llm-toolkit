"""Tests for /api/models — flat cross-host model index."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from llm_toolkit.discovery.types import LoadedModel, ModelInfo, RunnerSnapshot
from llm_toolkit.web.app import create_app

TOML = """
[[host]]
name = "drubuntu"
[[host.runner]]
type = "ollama"
url  = "http://drubuntu:11434"
gpu  = "3080ti"
[[host]]
name = "localhost"
[[host.runner]]
type = "ollama"
url  = "http://127.0.0.1:11434"
gpu  = "m3-max"
"""


def _client(tmp_path: Path) -> TestClient:
    hosts = tmp_path / "hosts.toml"
    hosts.write_text(TOML)
    app = create_app(db_path=tmp_path / "r.db", hosts_path=hosts)

    def fake_probe_factory(host_name, gpu):
        async def _probe(base_url, gpu_arg):
            return RunnerSnapshot(
                runner="ollama",
                base_url=base_url,
                gpu=gpu,
                version="0.5.7",
                reachable=True,
                error=None,
                installed_models=[ModelInfo(tag=f"model-{host_name}-a"),
                                  ModelInfo(tag="qwen3:8b")],
                loaded_models=[LoadedModel(tag="qwen3:8b")] if host_name == "drubuntu" else [],
            )
        return _probe

    # Each host returns a different snapshot
    adapter = app.state.ctx.adapters["ollama"]
    calls: dict[str, AsyncMock] = {
        "drubuntu": AsyncMock(side_effect=fake_probe_factory("drubuntu", "3080ti")),
        "localhost": AsyncMock(side_effect=fake_probe_factory("localhost", "m3-max")),
    }

    async def dispatch(base_url, gpu):
        if "drubuntu" in base_url:
            return await calls["drubuntu"](base_url, gpu)
        return await calls["localhost"](base_url, gpu)

    adapter.probe = dispatch
    return TestClient(app)


def test_models_index_flattens_across_hosts(tmp_path: Path):
    client = _client(tmp_path)
    r = client.get("/api/models")
    assert r.status_code == 200
    body = r.json()
    rows = body["models"]
    keys = {(m["tag"], m["host"], m["runner"], m["gpu"]) for m in rows}
    assert ("qwen3:8b", "drubuntu", "ollama", "3080ti") in keys
    assert ("qwen3:8b", "localhost", "ollama", "m3-max") in keys
    assert ("model-drubuntu-a", "drubuntu", "ollama", "3080ti") in keys


def test_loaded_flag(tmp_path: Path):
    client = _client(tmp_path)
    rows = client.get("/api/models").json()["models"]
    drubuntu_qwen = next(
        m for m in rows if m["tag"] == "qwen3:8b" and m["host"] == "drubuntu"
    )
    localhost_qwen = next(
        m for m in rows if m["tag"] == "qwen3:8b" and m["host"] == "localhost"
    )
    assert drubuntu_qwen["loaded"] is True
    assert localhost_qwen["loaded"] is False
