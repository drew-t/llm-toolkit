"""Tests for POST /api/runs."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from llm_toolkit.db import init_db
from llm_toolkit.web.app import create_app


def _seed_snapshot(db: Path) -> None:
    init_db(db)
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO host_snapshots (host, runner, gpu, runner_version, "
            "timestamp, state) VALUES (?, ?, ?, ?, ?, ?)",
            ("drubuntu", "ollama", "3080ti", "0.5.7", time.time(), "{}"),
        )
        conn.commit()


def _client(tmp_path: Path) -> TestClient:
    db = tmp_path / "r.db"
    _seed_snapshot(db)
    app = create_app(
        db_path=db,
        hosts_path=tmp_path / "h.toml",
        runs_dir=tmp_path / "runs",
    )
    return TestClient(app)


def test_post_run_inserts_pending_row(tmp_path: Path):
    with patch("llm_toolkit.jobs.queue.JobQueue.enqueue", autospec=True):
        client = _client(tmp_path)
        r = client.post(
            "/api/runs",
            json={
                "benchmark": "throughput_benchy",
                "model": "qwen3:8b",
                "host": "drubuntu",
                "runner": "ollama",
                "gpu": "3080ti",
                "base_url": "http://drubuntu:11434/v1",
                "args": {"pp": [2048], "tg": [256]},
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert isinstance(body["id"], int)
        assert body["status"] == "pending"

    db = tmp_path / "r.db"
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (body["id"],)).fetchone()
    assert row["status"] == "pending"
    assert row["benchmark"] == "throughput_benchy"
    assert row["model"] == "qwen3:8b"
    assert row["host"] == "drubuntu"
    assert row["runner_version"] == "0.5.7"


def test_post_run_rejects_unknown_benchmark(tmp_path: Path):
    client = _client(tmp_path)
    r = client.post(
        "/api/runs",
        json={
            "benchmark": "not-a-suite",
            "model": "qwen3:8b",
            "host": "drubuntu",
            "runner": "ollama",
            "gpu": "3080ti",
            "base_url": "http://drubuntu:11434/v1",
            "args": {},
        },
    )
    assert r.status_code == 400


def test_post_run_requires_fields(tmp_path: Path):
    client = _client(tmp_path)
    r = client.post("/api/runs", json={"benchmark": "throughput_benchy"})
    assert r.status_code == 422
