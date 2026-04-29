"""Result storage for benchmark runs.

Two backends:
- JsonlResultStore: append-only JSONL file. Original implementation, kept for
  legacy callers and the db-migrate importer.
- SqliteResultStore (default): SQLite-backed, queryable by host/runner/gpu/etc.

Use the module-level ResultStore(path) factory; it picks a backend based on
the file extension (.jsonl -> JSONL, anything else -> SQLite).
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from llm_toolkit.db import init_db


@dataclass
class BenchResult:
    """A single benchmark result entry."""

    benchmark: str
    model: str
    timestamp: float
    metrics: dict
    metadata: dict


class JsonlResultStore:
    """Append-only JSONL store. Same shape as the historical ResultStore."""

    def __init__(self, path: Path | str):
        self.path = Path(path)

    def append(self, result: BenchResult) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as f:
            f.write(json.dumps(asdict(result)) + "\n")

    def _load(self) -> list[BenchResult]:
        if not self.path.exists():
            return []
        out: list[BenchResult] = []
        for line in self.path.read_text().splitlines():
            line = line.strip()
            if line:
                out.append(BenchResult(**json.loads(line)))
        return out

    def query(
        self,
        *,
        benchmark: str | None = None,
        model: str | None = None,
        since: float | None = None,
    ) -> list[BenchResult]:
        results = self._load()
        if benchmark is not None:
            results = [r for r in results if r.benchmark == benchmark]
        if model is not None:
            results = [r for r in results if r.model == model]
        if since is not None:
            results = [r for r in results if r.timestamp >= since]
        return results

    def summary_table(
        self,
        results: list[BenchResult],
        pivot: str = "model",
        metric: str = "wall_time_s",
    ) -> str:
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
        if benchmark is not None:
            clauses.append("benchmark = ?"); args.append(benchmark)
        if model is not None:
            clauses.append("model = ?"); args.append(model)
        if host is not None:
            clauses.append("host = ?"); args.append(host)
        if runner is not None:
            clauses.append("runner = ?"); args.append(runner)
        if gpu is not None:
            clauses.append("gpu = ?"); args.append(gpu)
        if since is not None:
            clauses.append("timestamp >= ?"); args.append(since)
        sql = "SELECT benchmark, model, timestamp, metrics, metadata FROM results"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY timestamp DESC"
        if limit is not None:
            sql += " LIMIT ?"; args.append(limit)
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


def ResultStore(path: Path | str):
    """Factory: pick JSONL or SQLite backend based on file extension."""
    p = Path(path)
    if p.suffix == ".jsonl":
        return JsonlResultStore(p)
    return SqliteResultStore(p)
