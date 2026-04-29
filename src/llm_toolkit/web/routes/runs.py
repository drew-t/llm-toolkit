"""/api/runs read-only endpoints. Phase 3 adds POST/DELETE/WS."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter(prefix="/api/runs")


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    if d.get("args_json") is not None:
        d["args"] = json.loads(d["args_json"])
    if d.get("config_json") is not None:
        d["config"] = json.loads(d["config_json"])
    return d


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
        sql += " WHERE status = ?"; args.append(status)
    sql += " ORDER BY id DESC LIMIT ? OFFSET ?"; args += [limit, offset]
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
