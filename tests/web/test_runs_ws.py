"""Integration tests for WS /ws/runs/<id>.

These spin up the full app and exercise the full path:
POST /api/runs -> background subprocess -> WS streams logs -> WS closes."""

from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient

from llm_toolkit.db import init_db
from llm_toolkit.web.app import create_app


def test_ws_replays_log_for_finished_run(tmp_path: Path):
    db = tmp_path / "r.db"
    init_db(db)
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    log = runs_dir / "1.log"
    log.write_text("line one\nline two\n")
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO runs (id, status, benchmark, model, host, runner, "
            "gpu, args_json, started_at, finished_at, exit_code, log_path) "
            "VALUES (1, 'success', 'throughput_benchy', 'm', 'h', 'ollama', "
            "'g', '{}', ?, ?, 0, ?)",
            (time.time() - 10, time.time(), str(log)),
        )
        conn.commit()

    app = create_app(db_path=db, hosts_path=tmp_path / "h.toml", runs_dir=runs_dir)
    with TestClient(app) as client, client.websocket_connect("/ws/runs/1") as ws:
        messages = []
        try:
            while True:
                messages.append(ws.receive_text())
        except Exception:
            pass
    types_seen = [json.loads(m)["type"] for m in messages]
    lines = [json.loads(m).get("line") for m in messages if json.loads(m)["type"] == "log"]
    assert "line one" in lines and "line two" in lines
    assert types_seen[-1] == "finished"


def test_ws_streams_live_run(tmp_path: Path):
    db = tmp_path / "r.db"
    init_db(db)
    runs_dir = tmp_path / "runs"
    app = create_app(db_path=db, hosts_path=tmp_path / "h.toml", runs_dir=runs_dir)

    with TestClient(app) as client:
        with sqlite3.connect(db) as conn:
            conn.execute(
                "INSERT INTO host_snapshots (host, runner, gpu, runner_version, "
                "timestamp, state) VALUES ('h', 'ollama', 'g', '0.5.7', ?, '{}')",
                (time.time(),),
            )
            conn.commit()

        from llm_toolkit.web.routes import runs as runs_routes

        original = runs_routes.build_argv

        def fake_argv(*, benchmark, model, base_url, results_path, args):
            script = (
                "import time\n"
                "for i in range(3):\n"
                "    print(f'tick-{i}', flush=True); time.sleep(0.05)\n"
            )
            return [sys.executable, "-c", script]

        runs_routes.build_argv = fake_argv  # type: ignore[assignment]
        try:
            r = client.post(
                "/api/runs",
                json={
                    "benchmark": "throughput_benchy",
                    "model": "m",
                    "host": "h",
                    "runner": "ollama",
                    "gpu": "g",
                    "base_url": "http://h/v1",
                    "args": {},
                },
            )
            assert r.status_code == 201
            rid = r.json()["id"]

            with client.websocket_connect(f"/ws/runs/{rid}") as ws:
                messages = []
                try:
                    while True:
                        messages.append(ws.receive_text())
                except Exception:
                    pass
        finally:
            runs_routes.build_argv = original  # type: ignore[assignment]

    types_seen = [json.loads(m)["type"] for m in messages]
    assert "log" in types_seen
    assert types_seen[-1] == "finished"
    log_lines = [json.loads(m)["line"] for m in messages if json.loads(m)["type"] == "log"]
    assert any(line.startswith("tick-") for line in log_lines)
