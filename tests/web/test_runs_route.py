"""Tests for /api/runs read-only endpoints (Phase 1 — write path lives in Phase 3)."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from fastapi.testclient import TestClient

from llm_toolkit.db import init_db
from llm_toolkit.web.app import create_app


def _seed(db_path: Path) -> int:
    init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO runs (status, benchmark, model, host, runner, gpu, "
            "runner_version, args_json, started_at, finished_at, exit_code, log_path) "
            "VALUES ('success', 'throughput_benchy', 'qwen3:8b', 'drubuntu', 'ollama', "
            "'3080ti', '0.5.7', '{\"--pp\": [2048]}', ?, ?, 0, '/tmp/x.log')",
            (time.time() - 60, time.time()),
        )
        conn.commit()
        return cur.lastrowid


def _client(tmp_path: Path) -> tuple[TestClient, int]:
    db = tmp_path / "r.db"
    rid = _seed(db)
    app = create_app(db_path=db, hosts_path=tmp_path / "hosts.toml")
    return TestClient(app), rid


def test_list_runs(tmp_path: Path):
    client, _ = _client(tmp_path)
    r = client.get("/api/runs")
    assert r.status_code == 200
    body = r.json()
    assert len(body["runs"]) == 1
    assert body["runs"][0]["status"] == "success"


def test_filter_runs_by_status(tmp_path: Path):
    client, _ = _client(tmp_path)
    assert len(client.get("/api/runs?status=success").json()["runs"]) == 1
    assert client.get("/api/runs?status=failed").json()["runs"] == []


def test_get_single_run(tmp_path: Path):
    client, rid = _client(tmp_path)
    r = client.get(f"/api/runs/{rid}")
    assert r.status_code == 200
    assert r.json()["id"] == rid


def test_get_missing_run_404(tmp_path: Path):
    client, _ = _client(tmp_path)
    assert client.get("/api/runs/9999").status_code == 404
