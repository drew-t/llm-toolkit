"""Tests for /api/hosts."""

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
"""


def _make_app(tmp_path: Path) -> tuple[TestClient, Path]:
    hosts = tmp_path / "hosts.toml"
    hosts.write_text(TOML)
    db = tmp_path / "r.db"
    app = create_app(db_path=db, hosts_path=hosts)
    return TestClient(app), db


def _snap() -> RunnerSnapshot:
    return RunnerSnapshot(
        runner="ollama",
        base_url="http://drubuntu:11434",
        gpu="3080ti",
        version="0.5.7",
        reachable=True,
        error=None,
        installed_models=[ModelInfo(tag="qwen3:8b", size_bytes=5_000_000_000)],
        loaded_models=[LoadedModel(tag="qwen3:8b", vram_bytes=8_000_000_000)],
    )


def test_get_hosts_returns_snapshots(tmp_path: Path):
    client, _ = _make_app(tmp_path)
    client.app.state.ctx.adapters["ollama"].probe = AsyncMock(return_value=_snap())

    r = client.get("/api/hosts")
    assert r.status_code == 200
    body = r.json()
    assert body["hosts"][0]["name"] == "drubuntu"
    rs = body["hosts"][0]["runners"][0]
    assert rs["runner"] == "ollama"
    assert rs["reachable"] is True
    assert rs["version"] == "0.5.7"
    assert rs["gpu"] == "3080ti"
    assert rs["installed_models"][0]["tag"] == "qwen3:8b"


def test_post_hosts_refresh_forces_reprobe(tmp_path: Path):
    client, _ = _make_app(tmp_path)
    probe = AsyncMock(return_value=_snap())
    client.app.state.ctx.adapters["ollama"].probe = probe

    client.get("/api/hosts")     # first call: 1 probe
    client.get("/api/hosts")     # cached: still 1 probe
    client.post("/api/hosts/refresh")  # force re-probe
    assert probe.await_count == 2
