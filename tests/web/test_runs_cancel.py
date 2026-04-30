"""Tests for DELETE /api/runs/{id}."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from fastapi.testclient import TestClient

from llm_toolkit.db import init_db
from llm_toolkit.web.app import create_app


def _seed(db: Path, status: str = "running") -> int:
    init_db(db)
    with sqlite3.connect(db) as conn:
        cur = conn.execute(
            "INSERT INTO runs (status, benchmark, model, host, runner, gpu, "
            "args_json, started_at) VALUES (?, 'throughput_benchy', 'm', "
            "'h', 'ollama', 'g', '{}', ?)",
            (status, time.time()),
        )
        conn.commit()
        return cur.lastrowid


def test_cancel_unknown_run_returns_404(tmp_path: Path):
    db = tmp_path / "r.db"
    init_db(db)
    app = create_app(
        db_path=db,
        hosts_path=tmp_path / "h.toml",
        runs_dir=tmp_path / "runs",
    )
    with TestClient(app) as client:
        r = client.delete("/api/runs/9999")
        assert r.status_code == 404


def test_cancel_finished_run_409(tmp_path: Path):
    db = tmp_path / "r.db"
    rid = _seed(db, status="success")
    app = create_app(
        db_path=db,
        hosts_path=tmp_path / "h.toml",
        runs_dir=tmp_path / "runs",
    )
    with TestClient(app) as client:
        r = client.delete(f"/api/runs/{rid}")
        assert r.status_code == 409


def test_cancel_pending_or_running_signals_queue(tmp_path: Path):
    db = tmp_path / "r.db"
    rid = _seed(db, status="running")
    app = create_app(
        db_path=db,
        hosts_path=tmp_path / "h.toml",
        runs_dir=tmp_path / "runs",
    )
    called: list[int] = []
    with TestClient(app) as client:
        app.state.ctx.queue.cancel = lambda rid: called.append(rid) or True
        r = client.delete(f"/api/runs/{rid}")
        assert r.status_code == 200
        assert called == [rid]
