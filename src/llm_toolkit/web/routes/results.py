"""/api/results endpoints."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter(prefix="/api/results")

# Per-suite "headline" metric, used to default the Compare diff.
PRIMARY_METRICS = {
    "throughput_benchy": "tg_throughput",
    "context_scaling": "score",
    "classifier": "score",
    "coding": "score",
}


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    d["metrics"] = json.loads(d["metrics"])
    d["metadata"] = json.loads(d["metadata"])
    return d


@router.get("")
def list_results(
    request: Request,
    benchmark: str | None = Query(None),
    model: str | None = Query(None),
    host: str | None = Query(None),
    runner: str | None = Query(None),
    gpu: str | None = Query(None),
    since: float | None = Query(None),
    sort: str = Query("timestamp"),
    order: str = Query("desc"),
    limit: int = Query(500, le=5000),
    offset: int = Query(0, ge=0),
) -> dict:
    if sort not in {"timestamp", "benchmark", "model", "host", "runner", "gpu"}:
        raise HTTPException(400, f"unknown sort column: {sort}")
    if order not in {"asc", "desc"}:
        raise HTTPException(400, f"unknown order: {order}")

    clauses: list[str] = []
    args: list[Any] = []
    for col, val in [("benchmark", benchmark), ("model", model),
                     ("host", host), ("runner", runner), ("gpu", gpu)]:
        if val is not None:
            clauses.append(f"{col} = ?"); args.append(val)
    if since is not None:
        clauses.append("timestamp >= ?"); args.append(since)
    sql = "SELECT * FROM results"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += f" ORDER BY {sort} {order.upper()}"
    sql += " LIMIT ? OFFSET ?"; args += [limit, offset]

    with sqlite3.connect(request.app.state.ctx.db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = [_row_to_dict(r) for r in conn.execute(sql, args)]
    return {"results": rows}


@router.get("/{rid}")
def get_result(rid: int, request: Request) -> dict:
    with sqlite3.connect(request.app.state.ctx.db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM results WHERE id = ?", (rid,)).fetchone()
    if row is None:
        raise HTTPException(404, "result not found")
    return _row_to_dict(row)


@router.post("/compare")
def compare(payload: dict, request: Request) -> dict:
    ids = payload.get("ids") or []
    if len(ids) < 2:
        raise HTTPException(400, "need at least 2 ids")
    placeholders = ",".join("?" * len(ids))
    with sqlite3.connect(request.app.state.ctx.db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = list(conn.execute(
            f"SELECT * FROM results WHERE id IN ({placeholders})", ids
        ))
    by_id = {r["id"]: _row_to_dict(r) for r in rows}
    ordered = [by_id[i] for i in ids if i in by_id]
    if not ordered:
        raise HTTPException(404, "no results found")
    benchmark = ordered[0]["benchmark"]
    primary = PRIMARY_METRICS.get(benchmark, "tg_throughput")
    baseline = ordered[0]["metrics"].get(primary)
    out_rows = []
    for r in ordered:
        v = r["metrics"].get(primary)
        diff_pct = (
            round((v - baseline) / baseline * 100.0, 2)
            if baseline not in (None, 0) and v is not None else None
        )
        out_rows.append({**r, "diff_pct": diff_pct})
    return {"primary_metric": primary, "rows": out_rows}
