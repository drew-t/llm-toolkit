"""Smoke tests for the FastAPI app."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from llm_toolkit.web.app import create_app


def test_healthz(tmp_path: Path):
    app = create_app(db_path=tmp_path / "r.db", hosts_path=tmp_path / "hosts.toml")
    client = TestClient(app)
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_app_creates_db_on_first_request(tmp_path: Path):
    db = tmp_path / "r.db"
    app = create_app(db_path=db, hosts_path=tmp_path / "hosts.toml")
    client = TestClient(app)
    client.get("/healthz")
    assert db.exists()
