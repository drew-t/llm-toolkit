"""Run a single subprocess job: tee stdout, manage the run row, import results.

Lifecycle:
    1. Mark run as 'running', set started_at, broadcast status.
    2. Spawn the subprocess (stderr merged into stdout).
    3. For each line: append to log file, broadcast as a 'log' event.
    4. Concurrently watch cancel_event; on set, send SIGTERM with a 5s
       grace before SIGKILL. Mark run as 'cancelled' and short-circuit.
    5. On natural exit, parse the JSONL the CLI produced and insert rows
       into `results` tagged with run_id, host, runner, gpu (via metadata).
    6. Mark run as 'success' (exit==0) or 'failed' (non-zero) and broadcast
       a final 'finished' event. Close the broadcaster (sentinel posted).
"""

from __future__ import annotations

import asyncio
import signal
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Any

from llm_toolkit.jobs.broadcaster import Broadcaster
from llm_toolkit.jobs.events import JobEvent
from llm_toolkit.results import JsonlResultStore, SqliteResultStore

CANCEL_GRACE_S = 5.0


@dataclass
class RunSpec:
    run_id: int
    argv: list[str]
    log_path: Path
    results_path: Path
    host: str | None
    runner: str | None
    gpu: str | None
    benchmark: str
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)


async def run_subprocess(
    spec: RunSpec,
    *,
    db_path: Path,
    broadcaster: Broadcaster,
) -> None:
    spec.log_path.parent.mkdir(parents=True, exist_ok=True)
    log_fh = spec.log_path.open("w", buffering=1)

    try:
        _set_running(db_path, spec.run_id)
        await broadcaster.publish(JobEvent.status("running"))

        proc = await asyncio.create_subprocess_exec(
            *spec.argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        cancel_task = asyncio.create_task(_watch_cancel(spec, proc))
        try:
            await _stream_stdout(proc, log_fh, broadcaster)
            exit_code = await proc.wait()
        finally:
            cancel_task.cancel()

        if spec.cancel_event.is_set():
            _finalise(db_path, spec.run_id, status="cancelled", exit_code=exit_code)
            await broadcaster.publish(
                JobEvent.finished("cancelled", exit_code=exit_code, results_imported=0)
            )
            return

        imported = _import_results(db_path, spec)
        for row in imported:
            await broadcaster.publish(
                JobEvent.result(
                    result_id=row["id"],
                    benchmark=row["benchmark"],
                    model=row["model"],
                    metrics=row["metrics"],
                )
            )

        status = "success" if exit_code == 0 else "failed"
        _finalise(db_path, spec.run_id, status=status, exit_code=exit_code)
        await broadcaster.publish(
            JobEvent.finished(status, exit_code=exit_code, results_imported=len(imported))
        )
    except Exception as e:
        _finalise(db_path, spec.run_id, status="failed", exit_code=None, error=str(e))
        await broadcaster.publish(JobEvent.log(f"[worker] error: {e}"))
        await broadcaster.publish(JobEvent.finished("failed", exit_code=None, results_imported=0))
    finally:
        log_fh.close()
        await broadcaster.close()


async def _stream_stdout(
    proc: asyncio.subprocess.Process,
    log_fh: IO[str],
    broadcaster: Broadcaster,
) -> None:
    assert proc.stdout is not None
    while True:
        raw = await proc.stdout.readline()
        if not raw:
            return
        line = raw.decode(errors="replace").rstrip("\n")
        log_fh.write(line + "\n")
        await broadcaster.publish(JobEvent.log(line))


async def _watch_cancel(spec: RunSpec, proc: asyncio.subprocess.Process) -> None:
    try:
        await spec.cancel_event.wait()
    except asyncio.CancelledError:
        return
    if proc.returncode is not None:
        return
    proc.send_signal(signal.SIGTERM)
    try:
        await asyncio.wait_for(proc.wait(), timeout=CANCEL_GRACE_S)
    except TimeoutError:
        proc.kill()
        await proc.wait()


def _set_running(db: Path, run_id: int) -> None:
    with sqlite3.connect(db) as conn:
        conn.execute(
            "UPDATE runs SET status = 'running', started_at = ? WHERE id = ?",
            (time.time(), run_id),
        )
        conn.commit()


def _finalise(
    db: Path,
    run_id: int,
    *,
    status: str,
    exit_code: int | None,
    error: str | None = None,
) -> None:
    with sqlite3.connect(db) as conn:
        if error is not None:
            conn.execute(
                "UPDATE runs SET status = ?, exit_code = ?, finished_at = ?, "
                "config_json = json_set(COALESCE(config_json, '{}'), '$.error', ?) "
                "WHERE id = ?",
                (status, exit_code, time.time(), error, run_id),
            )
        else:
            conn.execute(
                "UPDATE runs SET status = ?, exit_code = ?, finished_at = ? WHERE id = ?",
                (status, exit_code, time.time(), run_id),
            )
        conn.commit()


def _import_results(db: Path, spec: RunSpec) -> list[dict[str, Any]]:
    if not spec.results_path.exists():
        return []
    sink = SqliteResultStore(db)
    src = JsonlResultStore(spec.results_path)
    inserted: list[dict[str, Any]] = []
    for r in src.query():
        meta = dict(r.metadata or {})
        meta["host"] = spec.host
        meta["runner"] = spec.runner
        meta["gpu"] = spec.gpu
        meta["run_id"] = spec.run_id
        r.metadata = meta
        sink.append(r)
        with sqlite3.connect(db) as conn:
            rid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        inserted.append(
            {
                "id": rid,
                "benchmark": r.benchmark,
                "model": r.model,
                "metrics": r.metrics,
            }
        )
    return inserted
