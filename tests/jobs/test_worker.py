"""Worker tests use a fake CLI: a python -c script printed through the same
code path the real CLI would take. Avoids needing `llm-toolkit` on PATH."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
import time
from pathlib import Path

import pytest

from llm_toolkit.db import init_db
from llm_toolkit.jobs.broadcaster import Broadcaster
from llm_toolkit.jobs.worker import RunSpec, run_subprocess


def _seed_run(db: Path, *, results_path: Path) -> int:
    init_db(db)
    with sqlite3.connect(db) as conn:
        cur = conn.execute(
            "INSERT INTO runs (status, benchmark, model, host, runner, gpu, "
            "args_json, log_path) "
            "VALUES ('pending', 'throughput_benchy', 'qwen3:8b', 'h', 'ollama', "
            "'3080ti', '{}', ?)",
            (str(results_path) + ".log",),
        )
        conn.commit()
        return cur.lastrowid


def _echo_argv(
    out_lines: list[str],
    jsonl_target: Path,
    jsonl_rows: list[dict] | None = None,
    exit_code: int = 0,
) -> list[str]:
    script = (
        "import json,sys,os\n"
        f"for line in {out_lines!r}:\n"
        "    print(line, flush=True)\n"
        f"rows = {jsonl_rows or []!r}\n"
        f"target = {str(jsonl_target)!r}\n"
        "if rows:\n"
        "    os.makedirs(os.path.dirname(target), exist_ok=True)\n"
        "    with open(target, 'w') as f:\n"
        "        for r in rows:\n"
        "            f.write(json.dumps(r) + '\\n')\n"
        f"sys.exit({exit_code})\n"
    )
    return [sys.executable, "-c", script]


@pytest.mark.asyncio
async def test_worker_streams_stdout_and_writes_log(tmp_path: Path):
    db = tmp_path / "r.db"
    results_path = tmp_path / "out.jsonl"
    rid = _seed_run(db, results_path=results_path)
    bc = Broadcaster()
    sub = bc.subscribe()

    spec = RunSpec(
        run_id=rid,
        argv=_echo_argv(["alpha", "beta"], results_path),
        log_path=tmp_path / f"{rid}.log",
        results_path=results_path,
        host="h",
        runner="ollama",
        gpu="3080ti",
        benchmark="throughput_benchy",
    )

    await run_subprocess(spec, db_path=db, broadcaster=bc)

    seen: list[str] = []
    while not sub.empty():
        e = sub.get_nowait()
        if e is None:
            break
        seen.append(e.type)
    assert "status" in seen
    assert "log" in seen
    assert "finished" in seen

    log_text = (tmp_path / f"{rid}.log").read_text()
    assert "alpha" in log_text
    assert "beta" in log_text


@pytest.mark.asyncio
async def test_worker_imports_results_with_run_id(tmp_path: Path):
    db = tmp_path / "r.db"
    results_path = tmp_path / "subdir" / "out.jsonl"
    rid = _seed_run(db, results_path=results_path)
    bc = Broadcaster()
    sub = bc.subscribe()
    rows = [
        {
            "benchmark": "throughput_benchy",
            "model": "qwen3:8b",
            "timestamp": time.time(),
            "metrics": {"tg_throughput": 73.4},
            "metadata": {"key": "row1"},
        }
    ]
    spec = RunSpec(
        run_id=rid,
        argv=_echo_argv(["done"], results_path, jsonl_rows=rows),
        log_path=tmp_path / f"{rid}.log",
        results_path=results_path,
        host="h",
        runner="ollama",
        gpu="3080ti",
        benchmark="throughput_benchy",
    )

    await run_subprocess(spec, db_path=db, broadcaster=bc)

    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        run = conn.execute("SELECT * FROM runs WHERE id = ?", (rid,)).fetchone()
        results = list(conn.execute("SELECT * FROM results WHERE run_id = ?", (rid,)))
    assert run["status"] == "success"
    assert run["exit_code"] == 0
    assert run["finished_at"] is not None
    assert len(results) == 1
    assert results[0]["host"] == "h"
    assert results[0]["runner"] == "ollama"
    assert results[0]["gpu"] == "3080ti"
    assert json.loads(results[0]["metrics"])["tg_throughput"] == 73.4

    # The 'result' event must carry the actual inserted row id (not 0).
    result_events = []
    while not sub.empty():
        e = sub.get_nowait()
        if e is None:
            break
        if e.type == "result":
            result_events.append(e)
    assert len(result_events) == 1
    assert result_events[0].payload["result_id"] == results[0]["id"]
    assert result_events[0].payload["result_id"] != 0


@pytest.mark.asyncio
async def test_worker_marks_failed_on_nonzero_exit(tmp_path: Path):
    db = tmp_path / "r.db"
    results_path = tmp_path / "out.jsonl"
    rid = _seed_run(db, results_path=results_path)
    bc = Broadcaster()
    spec = RunSpec(
        run_id=rid,
        argv=_echo_argv(["boom"], results_path, exit_code=2),
        log_path=tmp_path / f"{rid}.log",
        results_path=results_path,
        host="h",
        runner="ollama",
        gpu="3080ti",
        benchmark="throughput_benchy",
    )

    await run_subprocess(spec, db_path=db, broadcaster=bc)

    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        run = conn.execute("SELECT * FROM runs WHERE id = ?", (rid,)).fetchone()
    assert run["status"] == "failed"
    assert run["exit_code"] == 2


@pytest.mark.asyncio
async def test_worker_sigterm_on_cancel(tmp_path: Path):
    db = tmp_path / "r.db"
    results_path = tmp_path / "out.jsonl"
    rid = _seed_run(db, results_path=results_path)
    bc = Broadcaster()
    script = "import time,sys\nwhile True:\n    print('tick', flush=True)\n    time.sleep(0.05)\n"
    spec = RunSpec(
        run_id=rid,
        argv=[sys.executable, "-c", script],
        log_path=tmp_path / f"{rid}.log",
        results_path=results_path,
        host="h",
        runner="ollama",
        gpu="3080ti",
        benchmark="throughput_benchy",
    )

    task = asyncio.create_task(run_subprocess(spec, db_path=db, broadcaster=bc))
    await asyncio.sleep(0.2)
    spec.cancel_event.set()
    await asyncio.wait_for(task, timeout=10.0)

    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        run = conn.execute("SELECT * FROM runs WHERE id = ?", (rid,)).fetchone()
    assert run["status"] == "cancelled"
