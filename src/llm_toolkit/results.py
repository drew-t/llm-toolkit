"""Result storage for benchmark runs.

Two backends:
- `JsonlResultStore`: append-only JSONL file. Public surface is `append()`.
  Reading JSONL is done via the module-level `read_jsonl()` helper, used by
  the `db migrate` importer and the runs worker.
- `SqliteResultStore`: SQLite-backed. Owns query and summary_table — i.e.,
  every operation that wants an index. This is the canonical store.

Use the module-level `ResultStore(path)` factory; it picks a backend based
on the file extension (.jsonl -> JSONL writer; anything else -> SQLite).

The JSONL backend stays around for two reasons: (1) external callers
(notably TMNT's benchmarking scripts) still write `results.jsonl` files,
and (2) it's the input format for `db migrate`. New code should write
SQLite directly.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

from llm_toolkit.db import init_db


@dataclass
class BenchResult:
    """A single benchmark result entry."""

    benchmark: str
    model: str
    timestamp: float
    metrics: dict
    metadata: dict


class ResultWriter(Protocol):
    """The write-side interface every result backend satisfies."""

    def append(self, result: BenchResult) -> None: ...


def read_jsonl(path: Path | str) -> list[BenchResult]:
    """Read a JSONL result file. Returns [] if the file doesn't exist.

    Used by the `db migrate` CLI and the runs worker to import historical
    JSONL output into SQLite. Not a query interface — it loads the whole
    file into memory.
    """
    p = Path(path)
    if not p.exists():
        return []
    out: list[BenchResult] = []
    for line in p.read_text().splitlines():
        line = line.strip()
        if line:
            out.append(BenchResult(**json.loads(line)))
    return out


class JsonlResultStore:
    """Append-only JSONL writer. No query, no summary — use SqliteResultStore
    for those, or `read_jsonl()` for one-shot bulk reads (e.g. migrators)."""

    def __init__(self, path: Path | str):
        self.path = Path(path)

    def append(self, result: BenchResult) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as f:
            f.write(json.dumps(asdict(result)) + "\n")


class SqliteResultStore:
    """SQLite-backed result store. Queryable by host/runner/gpu/benchmark/model."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        init_db(self.path)

    def append(self, result: BenchResult) -> None:
        meta = result.metadata or {}
        host = meta.get("host")
        runner = meta.get("runner")
        gpu = meta.get("gpu")
        run_id = meta.get("run_id")
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                "INSERT INTO results "
                "(benchmark, model, host, runner, gpu, run_id, timestamp, "
                " metrics, metadata) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    result.benchmark,
                    result.model,
                    host,
                    runner,
                    gpu,
                    run_id,
                    result.timestamp,
                    json.dumps(result.metrics),
                    json.dumps(result.metadata),
                ),
            )
            conn.commit()

    def query(
        self,
        *,
        benchmark: str | None = None,
        model: str | None = None,
        host: str | None = None,
        runner: str | None = None,
        gpu: str | None = None,
        since: float | None = None,
        limit: int | None = None,
    ) -> list[BenchResult]:
        clauses: list[str] = []
        args: list[Any] = []
        for col, val in [
            ("benchmark", benchmark),
            ("model", model),
            ("host", host),
            ("runner", runner),
            ("gpu", gpu),
        ]:
            if val is not None:
                clauses.append(f"{col} = ?")
                args.append(val)
        if since is not None:
            clauses.append("timestamp >= ?")
            args.append(since)
        sql = "SELECT benchmark, model, timestamp, metrics, metadata FROM results"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY timestamp DESC"
        if limit is not None:
            sql += " LIMIT ?"
            args.append(limit)
        with sqlite3.connect(self.path) as conn:
            rows = list(conn.execute(sql, args))
        return [
            BenchResult(
                benchmark=r[0],
                model=r[1],
                timestamp=r[2],
                metrics=json.loads(r[3]),
                metadata=json.loads(r[4]),
            )
            for r in rows
        ]

    def summary_table(
        self,
        results: list[BenchResult],
        pivot: str = "model",
        metric: str = "wall_time_s",
    ) -> str:
        """Render a grouped average table over an in-memory result list.

        Takes results explicitly rather than re-querying so callers can shape
        the input (filter, paginate) before rendering.
        """
        if not results:
            return "(no results)"
        groups: dict[str, list[BenchResult]] = {}
        for r in results:
            key = getattr(r, pivot, "unknown")
            groups.setdefault(key, []).append(r)
        lines = []
        header = f"{'Name':<25} {metric:>12} {'Count':>6}"
        lines.append(header)
        lines.append("-" * len(header))
        for name, group in sorted(groups.items()):
            vals = [r.metrics.get(metric, 0) for r in group]
            avg = sum(vals) / len(vals) if vals else 0
            lines.append(f"{name:<25} {avg:>12.3f} {len(group):>6}")
        return "\n".join(lines)


def ResultStore(path: Path | str) -> ResultWriter:
    """Factory: pick JSONL or SQLite backend based on file extension.

    Returns a `ResultWriter` — the common interface is `append()` only.
    Callers that need to query or render summaries must construct a
    `SqliteResultStore` directly (or use `read_jsonl()` for a JSONL file).
    """
    p = Path(path)
    if p.suffix == ".jsonl":
        return JsonlResultStore(p)
    return SqliteResultStore(p)
