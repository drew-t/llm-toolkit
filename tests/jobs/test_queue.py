import asyncio
import sqlite3
import sys
import time
from pathlib import Path

import pytest

from llm_toolkit.db import init_db
from llm_toolkit.jobs.queue import JobQueue
from llm_toolkit.jobs.worker import RunSpec


def _seed_run(db: Path) -> int:
    init_db(db)
    with sqlite3.connect(db) as conn:
        cur = conn.execute(
            "INSERT INTO runs (status, benchmark, model, host, runner, gpu, "
            "args_json) VALUES ('pending', 'throughput_benchy', 'm', "
            "'h', 'ollama', 'g', '{}')"
        )
        conn.commit()
        return cur.lastrowid


def _echo_spec(rid: int, log_dir: Path, msg: str) -> RunSpec:
    script = f"print({msg!r}, flush=True)\n"
    return RunSpec(
        run_id=rid,
        argv=[sys.executable, "-c", script],
        log_path=log_dir / f"{rid}.log",
        results_path=log_dir / f"{rid}.jsonl",
        host="h",
        runner="ollama",
        gpu="g",
        benchmark="throughput_benchy",
    )


@pytest.mark.asyncio
async def test_enqueue_runs_in_order(tmp_path: Path):
    db = tmp_path / "r.db"
    q = JobQueue(db_path=db, runs_dir=tmp_path)
    await q.start()
    try:
        ids = [_seed_run(db) for _ in range(2)]
        for rid in ids:
            await q.enqueue(_echo_spec(rid, tmp_path, f"hello-{rid}"))
        deadline = time.time() + 5.0
        while time.time() < deadline:
            with sqlite3.connect(db) as conn:
                conn.row_factory = sqlite3.Row
                rows = list(conn.execute("SELECT status FROM runs WHERE id IN (?, ?)", ids))
            if all(r["status"] == "success" for r in rows):
                break
            await asyncio.sleep(0.05)
        with sqlite3.connect(db) as conn:
            conn.row_factory = sqlite3.Row
            rows = list(conn.execute("SELECT status FROM runs ORDER BY id"))
        assert [r["status"] for r in rows] == ["success", "success"]
    finally:
        await q.stop()


@pytest.mark.asyncio
async def test_cancel_running_job(tmp_path: Path):
    db = tmp_path / "r.db"
    q = JobQueue(db_path=db, runs_dir=tmp_path)
    await q.start()
    try:
        rid = _seed_run(db)
        spec = RunSpec(
            run_id=rid,
            argv=[
                sys.executable,
                "-c",
                "import time\nwhile True:\n  print('.', flush=True); time.sleep(0.05)\n",
            ],
            log_path=tmp_path / f"{rid}.log",
            results_path=tmp_path / f"{rid}.jsonl",
            host="h",
            runner="ollama",
            gpu="g",
            benchmark="throughput_benchy",
        )
        await q.enqueue(spec)
        await asyncio.sleep(0.3)
        assert q.cancel(rid) is True
        deadline = time.time() + 10.0
        while time.time() < deadline:
            with sqlite3.connect(db) as conn:
                row = conn.execute("SELECT status FROM runs WHERE id = ?", (rid,)).fetchone()
            if row[0] == "cancelled":
                break
            await asyncio.sleep(0.05)
        assert row[0] == "cancelled"
    finally:
        await q.stop()


@pytest.mark.asyncio
async def test_subscribe_returns_broadcaster_for_active_run(tmp_path: Path):
    db = tmp_path / "r.db"
    q = JobQueue(db_path=db, runs_dir=tmp_path)
    await q.start()
    try:
        rid = _seed_run(db)
        spec = RunSpec(
            run_id=rid,
            argv=[
                sys.executable,
                "-c",
                "import time\ntime.sleep(0.5)\nprint('hi')\n",
            ],
            log_path=tmp_path / f"{rid}.log",
            results_path=tmp_path / f"{rid}.jsonl",
            host="h",
            runner="ollama",
            gpu="g",
            benchmark="throughput_benchy",
        )
        await q.enqueue(spec)
        bc = None
        for _ in range(50):
            bc = q.broadcaster_for(rid)
            if bc is not None:
                break
            await asyncio.sleep(0.05)
        assert bc is not None
    finally:
        await q.stop()


@pytest.mark.asyncio
async def test_cancel_unknown_run_returns_false(tmp_path: Path):
    db = tmp_path / "r.db"
    q = JobQueue(db_path=db, runs_dir=tmp_path)
    await q.start()
    try:
        assert q.cancel(99999) is False
    finally:
        await q.stop()
