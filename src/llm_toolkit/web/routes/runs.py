"""/api/runs — list, get, create, cancel; plus WS at /ws/runs/{id}."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from llm_toolkit.jobs.argv import build_argv
from llm_toolkit.jobs.worker import RunSpec

router = APIRouter(prefix="/api/runs")


class CreateRunBody(BaseModel):
    benchmark: str
    model: str
    host: str
    runner: str
    gpu: str | None = None
    base_url: str
    args: dict[str, Any] = Field(default_factory=dict)


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    if d.get("args_json") is not None:
        d["args"] = json.loads(d["args_json"])
    if d.get("config_json") is not None:
        d["config"] = json.loads(d["config_json"])
    return d


def _latest_runner_version(db: Path, host: str, runner: str) -> str | None:
    with sqlite3.connect(db) as conn:
        row = conn.execute(
            "SELECT runner_version FROM host_snapshots "
            "WHERE host = ? AND runner = ? "
            "ORDER BY timestamp DESC LIMIT 1",
            (host, runner),
        ).fetchone()
    return row[0] if row else None


@router.get("")
def list_runs(
    request: Request,
    status: str | None = Query(None),
    limit: int = Query(200, le=2000),
    offset: int = Query(0, ge=0),
) -> dict:
    sql = "SELECT * FROM runs"
    args: list[Any] = []
    if status is not None:
        sql += " WHERE status = ?"
        args.append(status)
    sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
    args += [limit, offset]
    with sqlite3.connect(request.app.state.ctx.db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = [_row_to_dict(r) for r in conn.execute(sql, args)]
    return {"runs": rows}


@router.get("/{rid}")
def get_run(rid: int, request: Request) -> dict:
    with sqlite3.connect(request.app.state.ctx.db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (rid,)).fetchone()
    if row is None:
        raise HTTPException(404, "run not found")
    return _row_to_dict(row)


@router.post("", status_code=201)
async def create_run(body: CreateRunBody, request: Request) -> dict:
    ctx = request.app.state.ctx
    try:
        # Validate the benchmark before touching the DB.
        build_argv(
            benchmark=body.benchmark,
            model=body.model,
            base_url=body.base_url,
            results_path=str(ctx.runs_dir / "_validate.jsonl"),
            args=body.args,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    runner_version = _latest_runner_version(ctx.db_path, body.host, body.runner)
    args_json = json.dumps(body.args)

    with sqlite3.connect(ctx.db_path) as conn:
        cur = conn.execute(
            "INSERT INTO runs (status, benchmark, model, host, runner, gpu, "
            "runner_version, args_json, log_path) "
            "VALUES ('pending', ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                body.benchmark,
                body.model,
                body.host,
                body.runner,
                body.gpu,
                runner_version,
                args_json,
                "",
            ),
        )
        conn.commit()
        rid = cur.lastrowid
        log_path = ctx.runs_dir / f"{rid}.log"
        results_path = ctx.runs_dir / f"{rid}.jsonl"
        conn.execute("UPDATE runs SET log_path = ? WHERE id = ?", (str(log_path), rid))
        conn.commit()

    argv = build_argv(
        benchmark=body.benchmark,
        model=body.model,
        base_url=body.base_url,
        results_path=str(results_path),
        args=body.args,
    )
    spec = RunSpec(
        run_id=rid,
        argv=argv,
        log_path=log_path,
        results_path=results_path,
        host=body.host,
        runner=body.runner,
        gpu=body.gpu,
        benchmark=body.benchmark,
    )
    await ctx.queue.enqueue(spec)
    return {"id": rid, "status": "pending"}
