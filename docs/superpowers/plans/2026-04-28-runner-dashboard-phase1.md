# Runner Dashboard — Phase 1: Backend Foundation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the SQLite-backed result store, hosts config loader, runner discovery layer (Ollama / vLLM / llama-server adapters), and the read-only FastAPI surface for hosts, results, and models. After this phase, `curl http://127.0.0.1:7860/api/hosts` returns a snapshot of every configured runner; `/api/results` returns SQLite-stored history.

**Architecture:** New SQLite schema (`results`, `runs`, `host_snapshots`) lives at `~/.local/share/llm-toolkit/results.db`. `ResultStore` gains a SQLite backend that becomes the default. Three runner adapters implement a small `RunnerAdapter` Protocol and are dispatched by `hosts.toml`. FastAPI app under `llm_toolkit.web` exposes read-only REST endpoints, mounted via a new `llm-toolkit ui` subcommand.

**Tech Stack:** Python 3.12+, SQLite via stdlib `sqlite3`, FastAPI, uvicorn, httpx (already a dep). Tests use `pytest` and `httpx.MockTransport` for adapter HTTP mocking (no new test dep).

**Out of scope (deferred to Phase 2/3):** any frontend code, the `runs` write path / job runner / WebSocket, the Run page form, model pulls.

---

## File structure (Phase 1)

**New files (Python):**
- `src/llm_toolkit/db.py` — SQLite schema constants, `init_db()`, `connect()` helper.
- `src/llm_toolkit/discovery/__init__.py` — re-exports.
- `src/llm_toolkit/discovery/types.py` — `ModelInfo`, `LoadedModel`, `RunnerSnapshot`, `RunnerAdapter` Protocol.
- `src/llm_toolkit/discovery/hosts.py` — `HostsConfig` TOML loader.
- `src/llm_toolkit/discovery/ollama.py` — `OllamaAdapter`.
- `src/llm_toolkit/discovery/vllm.py` — `VLLMAdapter`.
- `src/llm_toolkit/discovery/llama_server.py` — `LlamaServerAdapter`.
- `src/llm_toolkit/discovery/cache.py` — TTL cache + `host_snapshots` writer.
- `src/llm_toolkit/web/__init__.py` — package marker.
- `src/llm_toolkit/web/app.py` — FastAPI app factory.
- `src/llm_toolkit/web/deps.py` — DI helpers (DB, hosts config, discovery).
- `src/llm_toolkit/web/routes/__init__.py` — package marker.
- `src/llm_toolkit/web/routes/hosts.py` — `/api/hosts` routes.
- `src/llm_toolkit/web/routes/results.py` — `/api/results` routes.
- `src/llm_toolkit/web/routes/runs.py` — `/api/runs` read-only routes.
- `src/llm_toolkit/web/routes/models.py` — `/api/models` route.

**Modified files:**
- `src/llm_toolkit/results.py` — refactor to add `SqliteResultStore`; rename existing class to `JsonlResultStore`; module-level `ResultStore(path)` factory chooses based on extension.
- `src/llm_toolkit/bench/runner.py` — add `ui` and `db migrate` subcommands.
- `pyproject.toml` — add `[project.optional-dependencies] web = ["fastapi>=0.115", "uvicorn[standard]>=0.34"]`.

**New tests:**
- `tests/test_db.py`
- `tests/test_results_sqlite.py`
- `tests/test_db_migrate_cli.py`
- `tests/discovery/__init__.py` (empty)
- `tests/discovery/test_hosts.py`
- `tests/discovery/test_ollama.py`
- `tests/discovery/test_vllm.py`
- `tests/discovery/test_llama_server.py`
- `tests/discovery/test_cache.py`
- `tests/web/__init__.py` (empty)
- `tests/web/test_app.py`
- `tests/web/test_hosts_route.py`
- `tests/web/test_results_route.py`
- `tests/web/test_runs_route.py`
- `tests/web/test_models_route.py`

---

## Task 1: Add web optional dependency + async test config

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Update pyproject.toml**

Update `[project.optional-dependencies]` and `[tool.pytest.ini_options]` so the final relevant blocks read:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "ruff>=0.9",
]
web = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.34",
]
train = [
    "unsloth",
    "datasets",
    "trl",
    "transformers",
    "torch>=2.0",
]
mlx = [
    "mlx-lm",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- [ ] **Step 2: Sync and verify**

Run: `uv sync --extra dev --extra web`
Expected: installs cleanly. Verify with `uv run python -c "import fastapi, uvicorn, pytest_asyncio"` (no error).

- [ ] **Step 3: Verify the existing test suite still passes**

Run: `uv run pytest -q`
Expected: existing tests pass (60 passed today).

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "build: add web + pytest-asyncio deps; enable asyncio_mode='auto'"
```

---

## Task 2: SQLite schema and connection helper

**Files:**
- Create: `src/llm_toolkit/db.py`
- Test: `tests/test_db.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_db.py`:

```python
"""Tests for db schema and connection helper."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from llm_toolkit.db import DEFAULT_DB_PATH, connect, init_db


def test_init_db_creates_tables(tmp_path: Path):
    db_path = tmp_path / "results.db"
    init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    assert {"results", "runs", "host_snapshots"} <= names


def test_init_db_is_idempotent(tmp_path: Path):
    db_path = tmp_path / "results.db"
    init_db(db_path)
    init_db(db_path)  # second call must not raise
    with sqlite3.connect(db_path) as conn:
        rows = list(
            conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' "
                "AND name='idx_results_timestamp'"
            )
        )
    assert len(rows) == 1


def test_connect_returns_wal_mode(tmp_path: Path):
    db_path = tmp_path / "results.db"
    init_db(db_path)
    with connect(db_path) as conn:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"


def test_default_db_path_is_under_local_share():
    assert "llm-toolkit" in str(DEFAULT_DB_PATH)
    assert str(DEFAULT_DB_PATH).endswith("results.db")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_db.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'llm_toolkit.db'`

- [ ] **Step 3: Implement db.py**

Create `src/llm_toolkit/db.py`:

```python
"""SQLite schema, connection helper, and init for llm-toolkit's result store."""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

DEFAULT_DB_PATH = Path(
    os.environ.get(
        "LLM_TOOLKIT_DB",
        str(Path.home() / ".local" / "share" / "llm-toolkit" / "results.db"),
    )
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS results (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  benchmark   TEXT NOT NULL,
  model       TEXT NOT NULL,
  host        TEXT,
  runner      TEXT,
  gpu         TEXT,
  run_id      INTEGER,
  timestamp   REAL NOT NULL,
  metrics     TEXT NOT NULL,
  metadata    TEXT NOT NULL,
  FOREIGN KEY(run_id) REFERENCES runs(id)
);

CREATE TABLE IF NOT EXISTS runs (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  status          TEXT NOT NULL,
  benchmark       TEXT NOT NULL,
  model           TEXT NOT NULL,
  host            TEXT,
  runner          TEXT,
  gpu             TEXT,
  runner_version  TEXT,
  args_json       TEXT NOT NULL,
  config_json     TEXT,
  started_at      REAL,
  finished_at     REAL,
  exit_code       INTEGER,
  log_path        TEXT
);

CREATE TABLE IF NOT EXISTS host_snapshots (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  host            TEXT NOT NULL,
  runner          TEXT NOT NULL,
  gpu             TEXT,
  runner_version  TEXT,
  timestamp       REAL NOT NULL,
  state           TEXT NOT NULL,
  config_json     TEXT
);

CREATE INDEX IF NOT EXISTS idx_results_bench_model ON results(benchmark, model);
CREATE INDEX IF NOT EXISTS idx_results_timestamp   ON results(timestamp);
CREATE INDEX IF NOT EXISTS idx_results_host_runner ON results(host, runner);
CREATE INDEX IF NOT EXISTS idx_results_host_gpu    ON results(host, gpu);
CREATE INDEX IF NOT EXISTS idx_snapshots_host_ts   ON host_snapshots(host, timestamp);
"""


def init_db(db_path: Path | str = DEFAULT_DB_PATH) -> None:
    """Create the database file (if missing) and ensure the schema is present."""
    p = Path(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(p) as conn:
        conn.executescript(SCHEMA)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.commit()


@contextmanager
def connect(db_path: Path | str = DEFAULT_DB_PATH) -> Iterator[sqlite3.Connection]:
    """Open a connection. Caller is responsible for transactions/commits."""
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
    finally:
        conn.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_db.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/llm_toolkit/db.py tests/test_db.py
git commit -m "feat(db): add sqlite schema, init, and connection helper"
```

---

## Task 3: SqliteResultStore + ResultStore factory

**Files:**
- Modify: `src/llm_toolkit/results.py`
- Test: `tests/test_results_sqlite.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_results_sqlite.py`:

```python
"""Tests for SqliteResultStore and the ResultStore factory."""

from __future__ import annotations

from pathlib import Path

from llm_toolkit.results import (
    BenchResult,
    JsonlResultStore,
    ResultStore,
    SqliteResultStore,
)


def _result(benchmark: str = "throughput_benchy", model: str = "qwen3:8b") -> BenchResult:
    return BenchResult(
        benchmark=benchmark,
        model=model,
        timestamp=1700000000.0,
        metrics={"tg_throughput": 114.3, "pp_throughput": 3923.0},
        metadata={"key": "c1_pp2048_tg128_d0", "host": "drubuntu",
                  "runner": "ollama", "gpu": "3080ti"},
    )


def test_sqlite_store_append_and_query(tmp_path: Path):
    store = SqliteResultStore(tmp_path / "r.db")
    store.append(_result(model="a"))
    store.append(_result(model="b"))
    rows = store.query()
    assert {r.model for r in rows} == {"a", "b"}
    assert rows[0].metrics["tg_throughput"] == 114.3


def test_sqlite_store_query_filters(tmp_path: Path):
    store = SqliteResultStore(tmp_path / "r.db")
    store.append(_result(model="a"))
    store.append(_result(model="b"))
    store.append(_result(model="b", benchmark="context_scaling"))
    rows = store.query(model="b", benchmark="throughput_benchy")
    assert len(rows) == 1


def test_sqlite_store_extracts_host_runner_gpu_from_metadata(tmp_path: Path):
    """When metadata contains host/runner/gpu, they get hoisted to columns."""
    import sqlite3
    store = SqliteResultStore(tmp_path / "r.db")
    store.append(_result())
    with sqlite3.connect(tmp_path / "r.db") as conn:
        row = conn.execute(
            "SELECT host, runner, gpu FROM results"
        ).fetchone()
    assert row == ("drubuntu", "ollama", "3080ti")


def test_factory_returns_jsonl_for_jsonl_path(tmp_path: Path):
    store = ResultStore(tmp_path / "out.jsonl")
    assert isinstance(store, JsonlResultStore)


def test_factory_returns_sqlite_for_db_path(tmp_path: Path):
    store = ResultStore(tmp_path / "out.db")
    assert isinstance(store, SqliteResultStore)


def test_jsonl_store_still_works(tmp_path: Path):
    store = JsonlResultStore(tmp_path / "out.jsonl")
    store.append(_result())
    rows = store.query()
    assert rows[0].model == "qwen3:8b"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_results_sqlite.py -v`
Expected: FAIL — `ImportError: cannot import name 'SqliteResultStore'`.

- [ ] **Step 3: Refactor results.py**

Replace `src/llm_toolkit/results.py` with:

```python
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
import time
from dataclasses import asdict, dataclass, field
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
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_results_sqlite.py tests/test_results.py -v`
Expected: all pass. The existing `tests/test_results.py` exercises the public `ResultStore` class — since `ResultStore(path)` is now a factory that returns `JsonlResultStore` for `.jsonl`, those tests must continue to pass unchanged. If they reference `ResultStore` as a class for `isinstance` checks, the test will fail; in that case update the test to use `JsonlResultStore`.

- [ ] **Step 5: Commit**

```bash
git add src/llm_toolkit/results.py tests/test_results_sqlite.py
git commit -m "feat(results): add SqliteResultStore; ResultStore is now a factory"
```

---

## Task 4: db migrate CLI subcommand

**Files:**
- Modify: `src/llm_toolkit/bench/runner.py` (add `db migrate` subparser + handler)
- Test: `tests/test_db_migrate_cli.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_db_migrate_cli.py`:

```python
"""Tests for `llm-toolkit db migrate` JSONL importer."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

from llm_toolkit.bench.runner import async_main
from llm_toolkit.results import BenchResult, JsonlResultStore


def _seed_jsonl(path: Path) -> None:
    store = JsonlResultStore(path)
    store.append(BenchResult(
        benchmark="throughput_benchy",
        model="qwen3:8b",
        timestamp=1700000000.0,
        metrics={"tg_throughput": 114.3},
        metadata={"key": "c1_pp2048_tg128_d0"},
    ))
    store.append(BenchResult(
        benchmark="throughput_benchy",
        model="tmnt-7b-q5",
        timestamp=1700000100.0,
        metrics={"tg_throughput": 142.1},
        metadata={"key": "c1_pp4096_tg128_d0"},
    ))


def _run_cli(argv: list[str]) -> None:
    with patch.object(sys, "argv", ["llm-toolkit", *argv]):
        asyncio.run(async_main())


def test_db_migrate_imports_jsonl_with_backfill(tmp_path: Path):
    src = tmp_path / "old.jsonl"
    db = tmp_path / "results.db"
    _seed_jsonl(src)

    _run_cli([
        "db", "migrate", str(src),
        "--db", str(db),
        "--host", "drubuntu",
        "--runner", "ollama",
        "--gpu", "3080ti",
    ])

    with sqlite3.connect(db) as conn:
        rows = list(
            conn.execute(
                "SELECT benchmark, model, host, runner, gpu, metrics FROM results"
            )
        )
    assert len(rows) == 2
    assert all(r[2] == "drubuntu" and r[3] == "ollama" and r[4] == "3080ti" for r in rows)
    assert json.loads(rows[0][5])["tg_throughput"] in (114.3, 142.1)


def test_db_migrate_no_backfill_leaves_columns_null(tmp_path: Path):
    src = tmp_path / "old.jsonl"
    db = tmp_path / "results.db"
    _seed_jsonl(src)

    _run_cli(["db", "migrate", str(src), "--db", str(db)])

    with sqlite3.connect(db) as conn:
        rows = list(conn.execute("SELECT host, runner, gpu FROM results"))
    assert all(r == (None, None, None) for r in rows)


def test_db_migrate_multiple_files(tmp_path: Path):
    a = tmp_path / "a.jsonl"
    b = tmp_path / "b.jsonl"
    db = tmp_path / "results.db"
    _seed_jsonl(a)
    _seed_jsonl(b)

    _run_cli(["db", "migrate", str(a), str(b), "--db", str(db)])

    with sqlite3.connect(db) as conn:
        n = conn.execute("SELECT COUNT(*) FROM results").fetchone()[0]
    assert n == 4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_db_migrate_cli.py -v`
Expected: FAIL — argparse rejects unknown subcommand `db`.

- [ ] **Step 3: Add the subparser and handler**

In `src/llm_toolkit/bench/runner.py`, in `async_main()`, after the `perf_p = ...` block and before `args = parser.parse_args()`, add:

```python
    db_p = sub.add_parser("db", help="Database utilities")
    db_sub = db_p.add_subparsers(dest="db_command")
    migrate_p = db_sub.add_parser("migrate", help="Import JSONL result files into SQLite")
    migrate_p.add_argument("paths", nargs="+", help="JSONL file(s) to import")
    migrate_p.add_argument("--db", type=str, default=None,
                           help="Target SQLite path (defaults to LLM_TOOLKIT_DB or "
                                "~/.local/share/llm-toolkit/results.db)")
    migrate_p.add_argument("--host", default=None, help="Backfill host column")
    migrate_p.add_argument("--runner", default=None, help="Backfill runner column")
    migrate_p.add_argument("--gpu", default=None, help="Backfill gpu column")
```

Update the dispatch block in `async_main()`:

```python
    if args.command == "bench":
        await _run_bench_command(args)
        return
    if args.command == "bench-perf":
        _run_bench_perf_command(args)
        return
    if args.command == "db":
        _run_db_command(args)
        return
    parser.print_help()
```

Add the handler at module level:

```python
def _run_db_command(args: argparse.Namespace) -> None:
    if args.db_command != "migrate":
        print("Usage: llm-toolkit db migrate <paths...> [--db PATH] "
              "[--host H] [--runner R] [--gpu G]")
        return
    from llm_toolkit.db import DEFAULT_DB_PATH
    from llm_toolkit.results import JsonlResultStore, SqliteResultStore

    db_path = Path(args.db) if args.db else DEFAULT_DB_PATH
    sink = SqliteResultStore(db_path)
    total = 0
    for src in args.paths:
        for r in JsonlResultStore(Path(src)).query():
            meta = dict(r.metadata or {})
            if args.host is not None:
                meta["host"] = args.host
            if args.runner is not None:
                meta["runner"] = args.runner
            if args.gpu is not None:
                meta["gpu"] = args.gpu
            r.metadata = meta
            sink.append(r)
            total += 1
    print(f"Imported {total} rows into {db_path}")
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_db_migrate_cli.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/llm_toolkit/bench/runner.py tests/test_db_migrate_cli.py
git commit -m "feat(cli): add 'db migrate' to import legacy JSONL into SQLite"
```

---

## Task 5: Discovery types + Protocol

**Files:**
- Create: `src/llm_toolkit/discovery/__init__.py`
- Create: `src/llm_toolkit/discovery/types.py`
- Create: `tests/discovery/__init__.py` (empty)
- Test: `tests/discovery/test_types.py`

- [ ] **Step 1: Write the failing test**

Create `tests/discovery/__init__.py` (empty file).

Create `tests/discovery/test_types.py`:

```python
"""Smoke tests for discovery types and the RunnerAdapter Protocol."""

from __future__ import annotations

from llm_toolkit.discovery.types import (
    LoadedModel,
    ModelInfo,
    RunnerAdapter,
    RunnerSnapshot,
)


def test_modelinfo_defaults():
    m = ModelInfo(tag="qwen3:8b")
    assert m.tag == "qwen3:8b"
    assert m.size_bytes is None
    assert m.modified is None


def test_runner_snapshot_defaults():
    s = RunnerSnapshot(
        runner="ollama",
        base_url="http://x:11434",
        gpu="3080ti",
        version="0.5.7",
        reachable=True,
        error=None,
        installed_models=[ModelInfo(tag="a")],
        loaded_models=[LoadedModel(tag="a", vram_bytes=8000000000, expires_at=None)],
        raw={},
    )
    assert s.reachable is True
    assert s.installed_models[0].tag == "a"


def test_runner_adapter_is_a_protocol():
    # Just confirms the Protocol can be referenced at runtime.
    assert RunnerAdapter is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/discovery/test_types.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Create the types module**

Create `src/llm_toolkit/discovery/__init__.py`:

```python
"""Runner discovery layer."""

from llm_toolkit.discovery.types import (
    LoadedModel,
    ModelInfo,
    RunnerAdapter,
    RunnerSnapshot,
)

__all__ = ["LoadedModel", "ModelInfo", "RunnerAdapter", "RunnerSnapshot"]
```

Create `src/llm_toolkit/discovery/types.py`:

```python
"""Dataclasses and the RunnerAdapter Protocol for the discovery layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class ModelInfo:
    tag: str
    size_bytes: int | None = None
    modified: float | None = None  # epoch seconds


@dataclass
class LoadedModel:
    tag: str
    vram_bytes: int | None = None
    expires_at: float | None = None  # epoch seconds


@dataclass
class RunnerSnapshot:
    runner: str            # 'ollama' | 'vllm' | 'llama-server'
    base_url: str
    gpu: str | None
    version: str | None
    reachable: bool
    error: str | None
    installed_models: list[ModelInfo] = field(default_factory=list)
    loaded_models: list[LoadedModel] = field(default_factory=list)
    raw: dict = field(default_factory=dict)


class RunnerAdapter(Protocol):
    """All runner adapters implement this interface."""

    name: str

    async def probe(self, base_url: str, gpu: str | None = None) -> RunnerSnapshot:
        ...
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/discovery/test_types.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/llm_toolkit/discovery/ tests/discovery/__init__.py tests/discovery/test_types.py
git commit -m "feat(discovery): add types and RunnerAdapter Protocol"
```

---

## Task 6: HostsConfig TOML loader

**Files:**
- Create: `src/llm_toolkit/discovery/hosts.py`
- Test: `tests/discovery/test_hosts.py`

- [ ] **Step 1: Write the failing test**

Create `tests/discovery/test_hosts.py`:

```python
"""Tests for hosts.toml loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from llm_toolkit.discovery.hosts import HostsConfig, RunnerEntry, load_hosts

SAMPLE_TOML = """
[[host]]
name = "drubuntu"

[[host.runner]]
type = "ollama"
url  = "http://drubuntu:11434"
gpu  = "3080ti"

[[host.runner]]
type = "llama-server"
url  = "http://drubuntu:8080"
gpu  = "3080ti"

[[host]]
name = "localhost"

[[host.runner]]
type = "ollama"
url  = "http://127.0.0.1:11434"
gpu  = "m3-max"
"""


def test_load_hosts_parses_two_hosts(tmp_path: Path):
    p = tmp_path / "hosts.toml"
    p.write_text(SAMPLE_TOML)
    cfg = load_hosts(p)
    assert isinstance(cfg, HostsConfig)
    assert [h.name for h in cfg.hosts] == ["drubuntu", "localhost"]
    drubuntu = cfg.hosts[0]
    assert len(drubuntu.runners) == 2
    assert drubuntu.runners[0] == RunnerEntry(
        type="ollama", url="http://drubuntu:11434", gpu="3080ti"
    )


def test_load_hosts_iter_runners(tmp_path: Path):
    p = tmp_path / "hosts.toml"
    p.write_text(SAMPLE_TOML)
    cfg = load_hosts(p)
    triples = [(h, r.type, r.url) for h, r in cfg.iter_runners()]
    assert ("drubuntu", "ollama", "http://drubuntu:11434") in triples
    assert ("localhost", "ollama", "http://127.0.0.1:11434") in triples
    assert len(triples) == 3


def test_load_hosts_missing_file_returns_empty(tmp_path: Path):
    cfg = load_hosts(tmp_path / "nope.toml")
    assert cfg.hosts == []


def test_load_hosts_unknown_runner_type_raises(tmp_path: Path):
    p = tmp_path / "hosts.toml"
    p.write_text(
        '[[host]]\nname = "x"\n'
        '[[host.runner]]\n'
        'type = "weird-thing"\n'
        'url = "http://x:8080"\n'
    )
    with pytest.raises(ValueError, match="weird-thing"):
        load_hosts(p)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/discovery/test_hosts.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'llm_toolkit.discovery.hosts'`.

- [ ] **Step 3: Implement hosts.py**

Create `src/llm_toolkit/discovery/hosts.py`:

```python
"""hosts.toml loader for the discovery layer."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

KNOWN_RUNNERS = {"ollama", "vllm", "llama-server"}

DEFAULT_HOSTS_PATH = Path(
    os.environ.get(
        "LLM_TOOLKIT_HOSTS",
        str(Path.home() / ".config" / "llm-toolkit" / "hosts.toml"),
    )
)


@dataclass(frozen=True)
class RunnerEntry:
    type: str            # 'ollama' | 'vllm' | 'llama-server'
    url: str
    gpu: str | None = None


@dataclass
class HostEntry:
    name: str
    runners: list[RunnerEntry] = field(default_factory=list)


@dataclass
class HostsConfig:
    hosts: list[HostEntry] = field(default_factory=list)

    def iter_runners(self) -> Iterator[tuple[str, RunnerEntry]]:
        """Yield (host_name, runner_entry) for every configured runner."""
        for host in self.hosts:
            for runner in host.runners:
                yield host.name, runner


def load_hosts(path: Path | str = DEFAULT_HOSTS_PATH) -> HostsConfig:
    """Load hosts.toml. Returns an empty config if the file does not exist."""
    p = Path(path)
    if not p.exists():
        return HostsConfig()
    with p.open("rb") as f:
        data = tomllib.load(f)

    hosts: list[HostEntry] = []
    for host_block in data.get("host", []):
        runners: list[RunnerEntry] = []
        for r in host_block.get("runner", []):
            rtype = r["type"]
            if rtype not in KNOWN_RUNNERS:
                raise ValueError(
                    f"Unknown runner type {rtype!r} in {p}. "
                    f"Known: {sorted(KNOWN_RUNNERS)}"
                )
            runners.append(RunnerEntry(type=rtype, url=r["url"], gpu=r.get("gpu")))
        hosts.append(HostEntry(name=host_block["name"], runners=runners))
    return HostsConfig(hosts=hosts)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/discovery/test_hosts.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/llm_toolkit/discovery/hosts.py tests/discovery/test_hosts.py
git commit -m "feat(discovery): add hosts.toml loader"
```

---

## Task 7: OllamaAdapter

**Files:**
- Create: `src/llm_toolkit/discovery/ollama.py`
- Test: `tests/discovery/test_ollama.py`

- [ ] **Step 1: Write the failing test**

Create `tests/discovery/test_ollama.py`:

```python
"""Tests for OllamaAdapter."""

from __future__ import annotations

import httpx
import pytest

from llm_toolkit.discovery.ollama import OllamaAdapter


def _mock_transport(handler):
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_ollama_happy_path():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.5.7"})
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={
                "models": [
                    {"name": "qwen3:8b", "size": 5_000_000_000, "modified_at": "2026-04-01T00:00:00Z"},
                    {"name": "llama3:8b", "size": 4_000_000_000, "modified_at": "2026-03-15T00:00:00Z"},
                ]
            })
        if request.url.path == "/api/ps":
            return httpx.Response(200, json={
                "models": [
                    {"name": "qwen3:8b", "size_vram": 8_000_000_000, "expires_at": "2026-04-28T16:00:00Z"},
                ]
            })
        return httpx.Response(404)

    adapter = OllamaAdapter(transport=_mock_transport(handler))
    snap = await adapter.probe("http://drubuntu:11434", gpu="3080ti")

    assert snap.runner == "ollama"
    assert snap.reachable is True
    assert snap.error is None
    assert snap.version == "0.5.7"
    assert snap.gpu == "3080ti"
    assert {m.tag for m in snap.installed_models} == {"qwen3:8b", "llama3:8b"}
    assert snap.installed_models[0].size_bytes in {5_000_000_000, 4_000_000_000}
    assert len(snap.loaded_models) == 1
    assert snap.loaded_models[0].tag == "qwen3:8b"
    assert snap.loaded_models[0].vram_bytes == 8_000_000_000


@pytest.mark.asyncio
async def test_ollama_unreachable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    adapter = OllamaAdapter(transport=_mock_transport(handler))
    snap = await adapter.probe("http://nope:11434", gpu=None)

    assert snap.reachable is False
    assert snap.error is not None
    assert snap.installed_models == []
    assert snap.loaded_models == []


@pytest.mark.asyncio
async def test_ollama_partial_only_version():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.5.7"})
        return httpx.Response(500, text="boom")

    adapter = OllamaAdapter(transport=_mock_transport(handler))
    snap = await adapter.probe("http://x:11434", gpu="3080ti")

    assert snap.reachable is True  # /version worked
    assert snap.version == "0.5.7"
    assert snap.installed_models == []
    assert snap.loaded_models == []
    assert snap.error is not None  # captured the failure
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/discovery/test_ollama.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'llm_toolkit.discovery.ollama'`.

- [ ] **Step 3: Implement OllamaAdapter**

Create `src/llm_toolkit/discovery/ollama.py`:

```python
"""Ollama runner adapter."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from llm_toolkit.discovery.types import LoadedModel, ModelInfo, RunnerSnapshot

TIMEOUT_S = 3.0


def _to_epoch(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


class OllamaAdapter:
    name = "ollama"

    def __init__(self, *, transport: httpx.BaseTransport | None = None):
        self._transport = transport

    async def probe(self, base_url: str, gpu: str | None = None) -> RunnerSnapshot:
        installed: list[ModelInfo] = []
        loaded: list[LoadedModel] = []
        version: str | None = None
        error: str | None = None
        reachable = False

        async with httpx.AsyncClient(
            base_url=base_url, timeout=TIMEOUT_S, transport=self._transport
        ) as client:
            try:
                r = await client.get("/api/version")
                r.raise_for_status()
                version = r.json().get("version")
                reachable = True
            except Exception as e:
                return RunnerSnapshot(
                    runner=self.name, base_url=base_url, gpu=gpu, version=None,
                    reachable=False, error=f"version: {e!r}",
                )

            try:
                r = await client.get("/api/tags")
                r.raise_for_status()
                for m in r.json().get("models", []):
                    installed.append(ModelInfo(
                        tag=m.get("name", ""),
                        size_bytes=m.get("size"),
                        modified=_to_epoch(m.get("modified_at")),
                    ))
            except Exception as e:
                error = f"tags: {e!r}"

            try:
                r = await client.get("/api/ps")
                r.raise_for_status()
                for m in r.json().get("models", []):
                    loaded.append(LoadedModel(
                        tag=m.get("name", ""),
                        vram_bytes=m.get("size_vram"),
                        expires_at=_to_epoch(m.get("expires_at")),
                    ))
            except Exception as e:
                error = f"{error}; ps: {e!r}" if error else f"ps: {e!r}"

        return RunnerSnapshot(
            runner=self.name, base_url=base_url, gpu=gpu, version=version,
            reachable=reachable, error=error,
            installed_models=installed, loaded_models=loaded,
            raw={},
        )
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/discovery/test_ollama.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/llm_toolkit/discovery/ollama.py tests/discovery/test_ollama.py pyproject.toml uv.lock
git commit -m "feat(discovery): add OllamaAdapter (version/tags/ps)"
```

---

## Task 8: VLLMAdapter

**Files:**
- Create: `src/llm_toolkit/discovery/vllm.py`
- Test: `tests/discovery/test_vllm.py`

- [ ] **Step 1: Write the failing test**

Create `tests/discovery/test_vllm.py`:

```python
"""Tests for VLLMAdapter."""

from __future__ import annotations

import httpx
import pytest

from llm_toolkit.discovery.vllm import VLLMAdapter


def _t(handler):
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_vllm_happy_path():
    metrics_text = (
        "# HELP vllm:gpu_cache_usage_perc GPU KV cache utilization\n"
        "# TYPE vllm:gpu_cache_usage_perc gauge\n"
        'vllm:gpu_cache_usage_perc{model_name="Qwen/Qwen3-8B"} 0.42\n'
    )

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/version":
            return httpx.Response(200, text="0.6.4")
        if req.url.path == "/v1/models":
            return httpx.Response(200, json={
                "data": [{"id": "Qwen/Qwen3-8B", "object": "model"}]
            })
        if req.url.path == "/metrics":
            return httpx.Response(200, text=metrics_text)
        return httpx.Response(404)

    snap = await VLLMAdapter(transport=_t(handler)).probe("http://x:8000", gpu="3080ti")
    assert snap.reachable is True
    assert snap.version == "0.6.4"
    assert [m.tag for m in snap.installed_models] == ["Qwen/Qwen3-8B"]
    assert [m.tag for m in snap.loaded_models] == ["Qwen/Qwen3-8B"]
    assert snap.raw["gpu_cache_usage_perc"] == 0.42


@pytest.mark.asyncio
async def test_vllm_metrics_optional():
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/version":
            return httpx.Response(200, text="0.6.4")
        if req.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "m"}]})
        return httpx.Response(404)  # /metrics absent

    snap = await VLLMAdapter(transport=_t(handler)).probe("http://x:8000")
    assert snap.reachable is True
    assert "gpu_cache_usage_perc" not in snap.raw  # absence is fine


@pytest.mark.asyncio
async def test_vllm_unreachable():
    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    snap = await VLLMAdapter(transport=_t(handler)).probe("http://nope:8000")
    assert snap.reachable is False
    assert snap.error is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/discovery/test_vllm.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement VLLMAdapter**

Create `src/llm_toolkit/discovery/vllm.py`:

```python
"""vLLM runner adapter."""

from __future__ import annotations

import re

import httpx

from llm_toolkit.discovery.types import LoadedModel, ModelInfo, RunnerSnapshot

TIMEOUT_S = 3.0
_KV_RE = re.compile(r"^vllm:gpu_cache_usage_perc\{[^}]*\}\s+([\d.eE+-]+)", re.MULTILINE)


class VLLMAdapter:
    name = "vllm"

    def __init__(self, *, transport: httpx.BaseTransport | None = None):
        self._transport = transport

    async def probe(self, base_url: str, gpu: str | None = None) -> RunnerSnapshot:
        installed: list[ModelInfo] = []
        version: str | None = None
        raw: dict = {}
        error: str | None = None
        reachable = False

        async with httpx.AsyncClient(
            base_url=base_url, timeout=TIMEOUT_S, transport=self._transport
        ) as client:
            try:
                r = await client.get("/version")
                r.raise_for_status()
                version = r.text.strip().split()[-1] or None
                reachable = True
            except Exception as e:
                return RunnerSnapshot(
                    runner=self.name, base_url=base_url, gpu=gpu, version=None,
                    reachable=False, error=f"version: {e!r}",
                )

            try:
                r = await client.get("/v1/models")
                r.raise_for_status()
                for m in r.json().get("data", []):
                    installed.append(ModelInfo(tag=m.get("id", "")))
            except Exception as e:
                error = f"models: {e!r}"

            try:
                r = await client.get("/metrics")
                if r.status_code == 200:
                    match = _KV_RE.search(r.text)
                    if match:
                        raw["gpu_cache_usage_perc"] = float(match.group(1))
            except Exception:
                # /metrics is optional; ignore failures silently
                pass

        # vLLM serves a single model per process — installed == loaded
        loaded = [LoadedModel(tag=m.tag) for m in installed]

        return RunnerSnapshot(
            runner=self.name, base_url=base_url, gpu=gpu, version=version,
            reachable=reachable, error=error,
            installed_models=installed, loaded_models=loaded,
            raw=raw,
        )
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/discovery/test_vllm.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/llm_toolkit/discovery/vllm.py tests/discovery/test_vllm.py
git commit -m "feat(discovery): add VLLMAdapter (version/models/metrics)"
```

---

## Task 9: LlamaServerAdapter

**Files:**
- Create: `src/llm_toolkit/discovery/llama_server.py`
- Test: `tests/discovery/test_llama_server.py`

- [ ] **Step 1: Write the failing test**

Create `tests/discovery/test_llama_server.py`:

```python
"""Tests for LlamaServerAdapter."""

from __future__ import annotations

import httpx
import pytest

from llm_toolkit.discovery.llama_server import LlamaServerAdapter


def _t(handler):
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_llama_server_happy_path():
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/props":
            return httpx.Response(200, json={
                "build_info": "build 4500 (abcdef0)",
                "default_generation_settings": {"n_ctx": 8192},
                "system_info": {"CUDA0": "NVIDIA GeForce RTX 3080 Ti, 12288 MiB"},
            })
        if req.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "tmnt-7b-q5"}]})
        if req.url.path == "/slots":
            return httpx.Response(200, json=[{"id": 0, "is_processing": True}])
        return httpx.Response(404)

    snap = await LlamaServerAdapter(transport=_t(handler)).probe("http://x:8080", gpu="3080ti")
    assert snap.reachable is True
    assert snap.version == "build 4500 (abcdef0)"
    assert [m.tag for m in snap.installed_models] == ["tmnt-7b-q5"]
    assert snap.loaded_models[0].tag == "tmnt-7b-q5"
    assert snap.raw["n_ctx"] == 8192
    assert snap.raw["slots"][0]["is_processing"] is True
    assert "CUDA0" in snap.raw["system_info"]


@pytest.mark.asyncio
async def test_llama_server_unreachable():
    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    snap = await LlamaServerAdapter(transport=_t(handler)).probe("http://nope:8080")
    assert snap.reachable is False
    assert snap.error is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/discovery/test_llama_server.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement LlamaServerAdapter**

Create `src/llm_toolkit/discovery/llama_server.py`:

```python
"""llama.cpp llama-server adapter."""

from __future__ import annotations

import httpx

from llm_toolkit.discovery.types import LoadedModel, ModelInfo, RunnerSnapshot

TIMEOUT_S = 3.0


class LlamaServerAdapter:
    name = "llama-server"

    def __init__(self, *, transport: httpx.BaseTransport | None = None):
        self._transport = transport

    async def probe(self, base_url: str, gpu: str | None = None) -> RunnerSnapshot:
        installed: list[ModelInfo] = []
        version: str | None = None
        raw: dict = {}
        error: str | None = None
        reachable = False

        async with httpx.AsyncClient(
            base_url=base_url, timeout=TIMEOUT_S, transport=self._transport
        ) as client:
            try:
                r = await client.get("/props")
                r.raise_for_status()
                props = r.json()
                version = props.get("build_info")
                gen_settings = props.get("default_generation_settings", {})
                if "n_ctx" in gen_settings:
                    raw["n_ctx"] = gen_settings["n_ctx"]
                if "system_info" in props:
                    raw["system_info"] = props["system_info"]
                reachable = True
            except Exception as e:
                return RunnerSnapshot(
                    runner=self.name, base_url=base_url, gpu=gpu, version=None,
                    reachable=False, error=f"props: {e!r}",
                )

            try:
                r = await client.get("/v1/models")
                r.raise_for_status()
                for m in r.json().get("data", []):
                    installed.append(ModelInfo(tag=m.get("id", "")))
            except Exception as e:
                error = f"models: {e!r}"

            try:
                r = await client.get("/slots")
                if r.status_code == 200:
                    raw["slots"] = r.json()
            except Exception:
                pass

        loaded = [LoadedModel(tag=m.tag) for m in installed]

        return RunnerSnapshot(
            runner=self.name, base_url=base_url, gpu=gpu, version=version,
            reachable=reachable, error=error,
            installed_models=installed, loaded_models=loaded,
            raw=raw,
        )
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/discovery/test_llama_server.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/llm_toolkit/discovery/llama_server.py tests/discovery/test_llama_server.py
git commit -m "feat(discovery): add LlamaServerAdapter (props/models/slots)"
```

---

## Task 10: Discovery cache + snapshot writer

**Files:**
- Create: `src/llm_toolkit/discovery/cache.py`
- Test: `tests/discovery/test_cache.py`

- [ ] **Step 1: Write the failing test**

Create `tests/discovery/test_cache.py`:

```python
"""Tests for the TTL cache and snapshot writer."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from llm_toolkit.db import init_db
from llm_toolkit.discovery.cache import DiscoveryCache
from llm_toolkit.discovery.types import RunnerSnapshot


def _snap(host: str, runner: str, gpu: str | None) -> RunnerSnapshot:
    return RunnerSnapshot(
        runner=runner, base_url=f"http://{host}:8080", gpu=gpu,
        version="x", reachable=True, error=None,
    )


@pytest.mark.asyncio
async def test_cache_hits_within_ttl(tmp_path: Path):
    db_path = tmp_path / "r.db"
    init_db(db_path)
    probe = AsyncMock(return_value=_snap("h", "ollama", "3080ti"))

    clock = [1000.0]
    cache = DiscoveryCache(db_path=db_path, ttl_s=10.0, clock=lambda: clock[0])
    s1 = await cache.get("h", "ollama", "http://h:11434", "3080ti", probe)
    clock[0] = 1005.0  # +5s, still inside TTL
    s2 = await cache.get("h", "ollama", "http://h:11434", "3080ti", probe)
    assert s1 is s2
    probe.assert_awaited_once()


@pytest.mark.asyncio
async def test_cache_misses_after_ttl(tmp_path: Path):
    db_path = tmp_path / "r.db"
    init_db(db_path)
    probe = AsyncMock(side_effect=[_snap("h", "ollama", "3080ti"),
                                   _snap("h", "ollama", "3080ti")])

    clock = [1000.0]
    cache = DiscoveryCache(db_path=db_path, ttl_s=10.0, clock=lambda: clock[0])
    await cache.get("h", "ollama", "http://h:11434", "3080ti", probe)
    clock[0] = 1011.0  # +11s, past TTL
    await cache.get("h", "ollama", "http://h:11434", "3080ti", probe)
    assert probe.await_count == 2


@pytest.mark.asyncio
async def test_cache_force_refresh_bypasses_ttl(tmp_path: Path):
    db_path = tmp_path / "r.db"
    init_db(db_path)
    probe = AsyncMock(return_value=_snap("h", "ollama", "3080ti"))

    cache = DiscoveryCache(db_path=db_path, ttl_s=10.0)
    await cache.get("h", "ollama", "http://h:11434", "3080ti", probe)
    await cache.get("h", "ollama", "http://h:11434", "3080ti", probe, force=True)
    assert probe.await_count == 2


@pytest.mark.asyncio
async def test_writes_host_snapshot_row(tmp_path: Path):
    db_path = tmp_path / "r.db"
    init_db(db_path)
    probe = AsyncMock(return_value=_snap("h", "ollama", "3080ti"))

    cache = DiscoveryCache(db_path=db_path, ttl_s=10.0)
    await cache.get("h", "ollama", "http://h:11434", "3080ti", probe)
    with sqlite3.connect(db_path) as conn:
        rows = list(conn.execute(
            "SELECT host, runner, gpu, runner_version, state FROM host_snapshots"
        ))
    assert len(rows) == 1
    assert rows[0][0] == "h" and rows[0][1] == "ollama" and rows[0][2] == "3080ti"
    state = json.loads(rows[0][4])
    assert state["reachable"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/discovery/test_cache.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement cache.py**

Create `src/llm_toolkit/discovery/cache.py`:

```python
"""TTL cache for runner snapshots, with persistence to host_snapshots."""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import asdict
from pathlib import Path
from typing import Awaitable, Callable

from llm_toolkit.discovery.types import RunnerSnapshot

ProbeFn = Callable[[str, str | None], Awaitable[RunnerSnapshot]]


class DiscoveryCache:
    """In-memory TTL cache keyed by (host, runner). Persists every probe to host_snapshots."""

    def __init__(
        self,
        *,
        db_path: Path | str,
        ttl_s: float = 10.0,
        clock: Callable[[], float] = time.time,
    ):
        self.db_path = Path(db_path)
        self.ttl_s = ttl_s
        self._clock = clock
        self._cache: dict[tuple[str, str], tuple[float, RunnerSnapshot]] = {}

    async def get(
        self,
        host: str,
        runner: str,
        base_url: str,
        gpu: str | None,
        probe: ProbeFn,
        *,
        force: bool = False,
    ) -> RunnerSnapshot:
        now = self._clock()
        key = (host, runner)
        if not force and key in self._cache:
            ts, snap = self._cache[key]
            if now - ts < self.ttl_s:
                return snap

        snapshot = await probe(base_url, gpu)
        self._cache[key] = (now, snapshot)
        self._persist(host, snapshot)
        return snapshot

    def invalidate(self, host: str | None = None, runner: str | None = None) -> None:
        if host is None and runner is None:
            self._cache.clear()
            return
        for key in list(self._cache):
            if (host is None or key[0] == host) and (runner is None or key[1] == runner):
                del self._cache[key]

    def _persist(self, host: str, snap: RunnerSnapshot) -> None:
        state = {
            "reachable": snap.reachable,
            "error": snap.error,
            "installed_models": [asdict(m) for m in snap.installed_models],
            "loaded_models": [asdict(m) for m in snap.loaded_models],
            "raw": snap.raw,
        }
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO host_snapshots "
                "(host, runner, gpu, runner_version, timestamp, state, config_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (host, snap.runner, snap.gpu, snap.version, self._clock(),
                 json.dumps(state), None),
            )
            conn.commit()
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/discovery/test_cache.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/llm_toolkit/discovery/cache.py tests/discovery/test_cache.py
git commit -m "feat(discovery): add TTL cache + host_snapshots persistence"
```

---

## Task 11: FastAPI app + ui subcommand

**Files:**
- Create: `src/llm_toolkit/web/__init__.py`
- Create: `src/llm_toolkit/web/app.py`
- Create: `src/llm_toolkit/web/deps.py`
- Modify: `src/llm_toolkit/bench/runner.py`
- Test: `tests/web/__init__.py` (empty)
- Test: `tests/web/test_app.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/web/__init__.py` (empty).

Create `tests/web/test_app.py`:

```python
"""Smoke tests for the FastAPI app."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from llm_toolkit.web.app import create_app


def test_healthz(tmp_path: Path):
    app = create_app(db_path=tmp_path / "r.db", hosts_path=tmp_path / "hosts.toml")
    client = TestClient(app)
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_app_creates_db_on_first_request(tmp_path: Path):
    db = tmp_path / "r.db"
    app = create_app(db_path=db, hosts_path=tmp_path / "hosts.toml")
    client = TestClient(app)
    client.get("/healthz")
    assert db.exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/web/test_app.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement app + deps**

Create `src/llm_toolkit/web/__init__.py`:

```python
"""FastAPI web UI for llm-toolkit."""
```

Create `src/llm_toolkit/web/deps.py`:

```python
"""Dependency-injection helpers for FastAPI handlers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from llm_toolkit.discovery.cache import DiscoveryCache
from llm_toolkit.discovery.hosts import HostsConfig, load_hosts
from llm_toolkit.discovery.llama_server import LlamaServerAdapter
from llm_toolkit.discovery.ollama import OllamaAdapter
from llm_toolkit.discovery.types import RunnerAdapter
from llm_toolkit.discovery.vllm import VLLMAdapter


@dataclass
class AppContext:
    db_path: Path
    hosts_path: Path
    cache: DiscoveryCache
    adapters: dict[str, RunnerAdapter]

    def hosts(self) -> HostsConfig:
        # Re-read on every call so editing hosts.toml is picked up without restart.
        return load_hosts(self.hosts_path)


def make_context(db_path: Path, hosts_path: Path) -> AppContext:
    return AppContext(
        db_path=db_path,
        hosts_path=hosts_path,
        cache=DiscoveryCache(db_path=db_path, ttl_s=10.0),
        adapters={
            "ollama": OllamaAdapter(),
            "vllm": VLLMAdapter(),
            "llama-server": LlamaServerAdapter(),
        },
    )
```

Create `src/llm_toolkit/web/app.py`:

```python
"""FastAPI app factory."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from llm_toolkit.db import DEFAULT_DB_PATH, init_db
from llm_toolkit.discovery.hosts import DEFAULT_HOSTS_PATH
from llm_toolkit.web.deps import make_context


def create_app(
    *,
    db_path: Path | str = DEFAULT_DB_PATH,
    hosts_path: Path | str = DEFAULT_HOSTS_PATH,
) -> FastAPI:
    db = Path(db_path)
    hosts = Path(hosts_path)
    init_db(db)

    app = FastAPI(title="llm-toolkit")
    app.state.ctx = make_context(db_path=db, hosts_path=hosts)

    @app.get("/healthz")
    def healthz() -> dict:
        return {"ok": True}

    return app
```

Add the `ui` subcommand to `src/llm_toolkit/bench/runner.py`. In `async_main()`, after the `db_p` block:

```python
    ui_p = sub.add_parser("ui", help="Start the web dashboard")
    ui_p.add_argument("--host", default="127.0.0.1")
    ui_p.add_argument("--port", type=int, default=7860)
    ui_p.add_argument("--db", type=str, default=None)
    ui_p.add_argument("--hosts-config", type=str, default=None)
```

In the dispatch block:

```python
    if args.command == "ui":
        _run_ui_command(args)
        return
```

Handler:

```python
def _run_ui_command(args: argparse.Namespace) -> None:
    import uvicorn
    from llm_toolkit.db import DEFAULT_DB_PATH
    from llm_toolkit.discovery.hosts import DEFAULT_HOSTS_PATH
    from llm_toolkit.web.app import create_app

    app = create_app(
        db_path=Path(args.db) if args.db else DEFAULT_DB_PATH,
        hosts_path=Path(args.hosts_config) if args.hosts_config else DEFAULT_HOSTS_PATH,
    )
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/web/test_app.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/llm_toolkit/web/ src/llm_toolkit/bench/runner.py tests/web/
git commit -m "feat(web): add FastAPI app factory + 'ui' subcommand"
```

---

## Task 12: /api/hosts route

**Files:**
- Create: `src/llm_toolkit/web/routes/__init__.py`
- Create: `src/llm_toolkit/web/routes/hosts.py`
- Modify: `src/llm_toolkit/web/app.py` (mount router)
- Test: `tests/web/test_hosts_route.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/web/test_hosts_route.py`:

```python
"""Tests for /api/hosts."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from llm_toolkit.discovery.types import LoadedModel, ModelInfo, RunnerSnapshot
from llm_toolkit.web.app import create_app

TOML = """
[[host]]
name = "drubuntu"
[[host.runner]]
type = "ollama"
url  = "http://drubuntu:11434"
gpu  = "3080ti"
"""


def _make_app(tmp_path: Path) -> tuple[TestClient, Path]:
    hosts = tmp_path / "hosts.toml"
    hosts.write_text(TOML)
    db = tmp_path / "r.db"
    app = create_app(db_path=db, hosts_path=hosts)
    return TestClient(app), db


def _snap() -> RunnerSnapshot:
    return RunnerSnapshot(
        runner="ollama",
        base_url="http://drubuntu:11434",
        gpu="3080ti",
        version="0.5.7",
        reachable=True,
        error=None,
        installed_models=[ModelInfo(tag="qwen3:8b", size_bytes=5_000_000_000)],
        loaded_models=[LoadedModel(tag="qwen3:8b", vram_bytes=8_000_000_000)],
    )


def test_get_hosts_returns_snapshots(tmp_path: Path):
    client, _ = _make_app(tmp_path)
    client.app.state.ctx.adapters["ollama"].probe = AsyncMock(return_value=_snap())

    r = client.get("/api/hosts")
    assert r.status_code == 200
    body = r.json()
    assert body["hosts"][0]["name"] == "drubuntu"
    rs = body["hosts"][0]["runners"][0]
    assert rs["runner"] == "ollama"
    assert rs["reachable"] is True
    assert rs["version"] == "0.5.7"
    assert rs["gpu"] == "3080ti"
    assert rs["installed_models"][0]["tag"] == "qwen3:8b"


def test_post_hosts_refresh_forces_reprobe(tmp_path: Path):
    client, _ = _make_app(tmp_path)
    probe = AsyncMock(return_value=_snap())
    client.app.state.ctx.adapters["ollama"].probe = probe

    client.get("/api/hosts")     # first call: 1 probe
    client.get("/api/hosts")     # cached: still 1 probe
    client.post("/api/hosts/refresh")  # force re-probe
    assert probe.await_count == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/web/test_hosts_route.py -v`
Expected: FAIL — `404` or import error.

- [ ] **Step 3: Implement the route**

Create `src/llm_toolkit/web/routes/__init__.py` (empty file).

Create `src/llm_toolkit/web/routes/hosts.py`:

```python
"""GET /api/hosts and POST /api/hosts/refresh."""

from __future__ import annotations

import asyncio
from dataclasses import asdict

from fastapi import APIRouter, Request

from llm_toolkit.discovery.types import RunnerSnapshot

router = APIRouter(prefix="/api/hosts")


def _snapshot_to_dict(snap: RunnerSnapshot) -> dict:
    return {
        "runner": snap.runner,
        "base_url": snap.base_url,
        "gpu": snap.gpu,
        "version": snap.version,
        "reachable": snap.reachable,
        "error": snap.error,
        "installed_models": [asdict(m) for m in snap.installed_models],
        "loaded_models": [asdict(m) for m in snap.loaded_models],
        "raw": snap.raw,
    }


async def _probe_all(ctx, *, force: bool) -> list[dict]:
    cfg = ctx.hosts()
    out: list[dict] = []
    for host in cfg.hosts:
        runner_dicts: list[dict] = []
        coros = []
        entries = []
        for entry in host.runners:
            adapter = ctx.adapters.get(entry.type)
            if adapter is None:
                continue
            entries.append(entry)
            coros.append(
                ctx.cache.get(
                    host.name, entry.type, entry.url, entry.gpu, adapter.probe, force=force
                )
            )
        snaps = await asyncio.gather(*coros, return_exceptions=False)
        for snap in snaps:
            runner_dicts.append(_snapshot_to_dict(snap))
        out.append({"name": host.name, "runners": runner_dicts})
    return out


@router.get("")
async def list_hosts(request: Request) -> dict:
    return {"hosts": await _probe_all(request.app.state.ctx, force=False)}


@router.post("/refresh")
async def refresh_hosts(request: Request) -> dict:
    return {"hosts": await _probe_all(request.app.state.ctx, force=True)}
```

In `src/llm_toolkit/web/app.py`, after the `app.state.ctx = ...` line, add:

```python
    from llm_toolkit.web.routes import hosts as hosts_routes
    app.include_router(hosts_routes.router)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/web/test_hosts_route.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/llm_toolkit/web/routes/ src/llm_toolkit/web/app.py tests/web/test_hosts_route.py
git commit -m "feat(web): add GET /api/hosts and POST /api/hosts/refresh"
```

---

## Task 13: /api/results route

**Files:**
- Create: `src/llm_toolkit/web/routes/results.py`
- Modify: `src/llm_toolkit/web/app.py` (mount router)
- Test: `tests/web/test_results_route.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/web/test_results_route.py`:

```python
"""Tests for /api/results."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from llm_toolkit.results import BenchResult, SqliteResultStore
from llm_toolkit.web.app import create_app


def _seed(db_path: Path) -> None:
    store = SqliteResultStore(db_path)
    store.append(BenchResult(
        benchmark="throughput_benchy", model="qwen3:8b",
        timestamp=1000.0,
        metrics={"tg_throughput": 114.3, "pp_throughput": 3923.0},
        metadata={"host": "drubuntu", "runner": "ollama", "gpu": "3080ti"},
    ))
    store.append(BenchResult(
        benchmark="throughput_benchy", model="qwen3:8b",
        timestamp=2000.0,
        metrics={"tg_throughput": 142.1, "pp_throughput": 9421.0},
        metadata={"host": "drubuntu", "runner": "llama-server", "gpu": "3080ti"},
    ))
    store.append(BenchResult(
        benchmark="context_scaling", model="qwen3:8b",
        timestamp=3000.0,
        metrics={"score": 0.91},
        metadata={"host": "localhost", "runner": "ollama", "gpu": "m3-max"},
    ))


def _client(tmp_path: Path) -> TestClient:
    db = tmp_path / "r.db"
    _seed(db)
    return TestClient(create_app(db_path=db, hosts_path=tmp_path / "hosts.toml"))


def test_list_default_sort_desc(tmp_path: Path):
    r = _client(tmp_path).get("/api/results")
    assert r.status_code == 200
    body = r.json()
    assert [row["timestamp"] for row in body["results"]] == [3000.0, 2000.0, 1000.0]


def test_filter_by_runner(tmp_path: Path):
    r = _client(tmp_path).get("/api/results?runner=llama-server")
    assert [row["metrics"]["tg_throughput"] for row in r.json()["results"]] == [142.1]


def test_filter_by_benchmark_and_host(tmp_path: Path):
    r = _client(tmp_path).get("/api/results?benchmark=throughput_benchy&host=drubuntu")
    assert len(r.json()["results"]) == 2


def test_get_single_result(tmp_path: Path):
    client = _client(tmp_path)
    listing = client.get("/api/results").json()["results"]
    rid = listing[0]["id"]
    r = client.get(f"/api/results/{rid}")
    assert r.status_code == 200
    assert r.json()["id"] == rid


def test_compare_returns_baseline_diffs(tmp_path: Path):
    client = _client(tmp_path)
    listing = client.get("/api/results?benchmark=throughput_benchy").json()["results"]
    ids = [row["id"] for row in listing]
    r = client.post("/api/results/compare", json={"ids": ids})
    assert r.status_code == 200
    body = r.json()
    assert len(body["rows"]) == 2
    assert body["primary_metric"] == "tg_throughput"
    # Whichever row was first becomes the baseline (diff_pct == 0)
    diffs = [row["diff_pct"] for row in body["rows"]]
    assert 0.0 in diffs
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/web/test_results_route.py -v`
Expected: FAIL — 404 / module not found.

- [ ] **Step 3: Implement the route**

Create `src/llm_toolkit/web/routes/results.py`:

```python
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
```

In `src/llm_toolkit/web/app.py`, after the hosts router include:

```python
    from llm_toolkit.web.routes import results as results_routes
    app.include_router(results_routes.router)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/web/test_results_route.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/llm_toolkit/web/routes/results.py src/llm_toolkit/web/app.py tests/web/test_results_route.py
git commit -m "feat(web): add GET /api/results, GET /api/results/{id}, POST /api/results/compare"
```

---

## Task 14: /api/runs read-only route

**Files:**
- Create: `src/llm_toolkit/web/routes/runs.py`
- Modify: `src/llm_toolkit/web/app.py` (mount router)
- Test: `tests/web/test_runs_route.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/web/test_runs_route.py`:

```python
"""Tests for /api/runs read-only endpoints (Phase 1 — write path lives in Phase 3)."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from fastapi.testclient import TestClient

from llm_toolkit.db import init_db
from llm_toolkit.web.app import create_app


def _seed(db_path: Path) -> int:
    init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO runs (status, benchmark, model, host, runner, gpu, "
            "runner_version, args_json, started_at, finished_at, exit_code, log_path) "
            "VALUES ('success', 'throughput_benchy', 'qwen3:8b', 'drubuntu', 'ollama', "
            "'3080ti', '0.5.7', '{\"--pp\": [2048]}', ?, ?, 0, '/tmp/x.log')",
            (time.time() - 60, time.time()),
        )
        conn.commit()
        return cur.lastrowid


def _client(tmp_path: Path) -> tuple[TestClient, int]:
    db = tmp_path / "r.db"
    rid = _seed(db)
    app = create_app(db_path=db, hosts_path=tmp_path / "hosts.toml")
    return TestClient(app), rid


def test_list_runs(tmp_path: Path):
    client, _ = _client(tmp_path)
    r = client.get("/api/runs")
    assert r.status_code == 200
    body = r.json()
    assert len(body["runs"]) == 1
    assert body["runs"][0]["status"] == "success"


def test_filter_runs_by_status(tmp_path: Path):
    client, _ = _client(tmp_path)
    assert len(client.get("/api/runs?status=success").json()["runs"]) == 1
    assert client.get("/api/runs?status=failed").json()["runs"] == []


def test_get_single_run(tmp_path: Path):
    client, rid = _client(tmp_path)
    r = client.get(f"/api/runs/{rid}")
    assert r.status_code == 200
    assert r.json()["id"] == rid


def test_get_missing_run_404(tmp_path: Path):
    client, _ = _client(tmp_path)
    assert client.get("/api/runs/9999").status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/web/test_runs_route.py -v`
Expected: FAIL — 404 / not implemented.

- [ ] **Step 3: Implement the route**

Create `src/llm_toolkit/web/routes/runs.py`:

```python
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
```

In `src/llm_toolkit/web/app.py`, after the results router include:

```python
    from llm_toolkit.web.routes import runs as runs_routes
    app.include_router(runs_routes.router)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/web/test_runs_route.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/llm_toolkit/web/routes/runs.py src/llm_toolkit/web/app.py tests/web/test_runs_route.py
git commit -m "feat(web): add read-only /api/runs endpoints"
```

---

## Task 15: /api/models route

**Files:**
- Create: `src/llm_toolkit/web/routes/models.py`
- Modify: `src/llm_toolkit/web/app.py` (mount router)
- Test: `tests/web/test_models_route.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/web/test_models_route.py`:

```python
"""Tests for /api/models — flat cross-host model index."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from llm_toolkit.discovery.types import LoadedModel, ModelInfo, RunnerSnapshot
from llm_toolkit.web.app import create_app

TOML = """
[[host]]
name = "drubuntu"
[[host.runner]]
type = "ollama"
url  = "http://drubuntu:11434"
gpu  = "3080ti"
[[host]]
name = "localhost"
[[host.runner]]
type = "ollama"
url  = "http://127.0.0.1:11434"
gpu  = "m3-max"
"""


def _client(tmp_path: Path) -> TestClient:
    hosts = tmp_path / "hosts.toml"
    hosts.write_text(TOML)
    app = create_app(db_path=tmp_path / "r.db", hosts_path=hosts)

    def fake_probe_factory(host_name, gpu):
        async def _probe(base_url, gpu_arg):
            return RunnerSnapshot(
                runner="ollama",
                base_url=base_url,
                gpu=gpu,
                version="0.5.7",
                reachable=True,
                error=None,
                installed_models=[ModelInfo(tag=f"model-{host_name}-a"),
                                  ModelInfo(tag="qwen3:8b")],
                loaded_models=[LoadedModel(tag="qwen3:8b")] if host_name == "drubuntu" else [],
            )
        return _probe

    # Each host returns a different snapshot
    adapter = app.state.ctx.adapters["ollama"]
    calls: dict[str, AsyncMock] = {
        "drubuntu": AsyncMock(side_effect=fake_probe_factory("drubuntu", "3080ti")),
        "localhost": AsyncMock(side_effect=fake_probe_factory("localhost", "m3-max")),
    }

    async def dispatch(base_url, gpu):
        if "drubuntu" in base_url:
            return await calls["drubuntu"](base_url, gpu)
        return await calls["localhost"](base_url, gpu)

    adapter.probe = dispatch
    return TestClient(app)


def test_models_index_flattens_across_hosts(tmp_path: Path):
    client = _client(tmp_path)
    r = client.get("/api/models")
    assert r.status_code == 200
    body = r.json()
    rows = body["models"]
    keys = {(m["tag"], m["host"], m["runner"], m["gpu"]) for m in rows}
    assert ("qwen3:8b", "drubuntu", "ollama", "3080ti") in keys
    assert ("qwen3:8b", "localhost", "ollama", "m3-max") in keys
    assert ("model-drubuntu-a", "drubuntu", "ollama", "3080ti") in keys


def test_loaded_flag(tmp_path: Path):
    client = _client(tmp_path)
    rows = client.get("/api/models").json()["models"]
    drubuntu_qwen = next(
        m for m in rows if m["tag"] == "qwen3:8b" and m["host"] == "drubuntu"
    )
    localhost_qwen = next(
        m for m in rows if m["tag"] == "qwen3:8b" and m["host"] == "localhost"
    )
    assert drubuntu_qwen["loaded"] is True
    assert localhost_qwen["loaded"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/web/test_models_route.py -v`
Expected: FAIL — 404 / not implemented.

- [ ] **Step 3: Implement the route**

Create `src/llm_toolkit/web/routes/models.py`:

```python
"""/api/models — flat cross-host model index."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/models")


@router.get("")
async def list_models(request: Request) -> dict:
    ctx = request.app.state.ctx
    cfg = ctx.hosts()
    rows: list[dict] = []
    for host in cfg.hosts:
        coros = []
        entries = []
        for entry in host.runners:
            adapter = ctx.adapters.get(entry.type)
            if adapter is None:
                continue
            entries.append(entry)
            coros.append(
                ctx.cache.get(host.name, entry.type, entry.url, entry.gpu, adapter.probe)
            )
        snaps = await asyncio.gather(*coros, return_exceptions=False)
        for entry, snap in zip(entries, snaps):
            loaded_tags = {m.tag for m in snap.loaded_models}
            for m in snap.installed_models:
                rows.append({
                    "tag": m.tag,
                    "host": host.name,
                    "runner": entry.type,
                    "gpu": entry.gpu,
                    "loaded": m.tag in loaded_tags,
                    "size_bytes": m.size_bytes,
                })
    return {"models": rows}
```

In `src/llm_toolkit/web/app.py`, after the runs router include:

```python
    from llm_toolkit.web.routes import models as models_routes
    app.include_router(models_routes.router)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/web/test_models_route.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/llm_toolkit/web/routes/models.py src/llm_toolkit/web/app.py tests/web/test_models_route.py
git commit -m "feat(web): add GET /api/models cross-host index"
```

---

## Task 16: Final Phase 1 verification

**Files:** none — verification only.

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest -v`
Expected: every test in the project passes (existing tests + the ~30 new ones from this phase).

- [ ] **Step 2: Run lint**

Run: `uv run ruff check src/ tests/`
Expected: `All checks passed!`

- [ ] **Step 3: Smoke-test the live server**

Create a temporary `hosts.toml`:

```bash
mkdir -p ~/.config/llm-toolkit
cat > ~/.config/llm-toolkit/hosts.toml <<'EOF'
[[host]]
name = "drubuntu"
[[host.runner]]
type = "ollama"
url  = "http://drubuntu:11434"
gpu  = "3080ti"

[[host]]
name = "localhost"
[[host.runner]]
type = "ollama"
url  = "http://127.0.0.1:11434"
gpu  = "m3-max"
EOF
```

Run the UI: `uv run llm-toolkit ui --port 7860`

In another terminal, hit each endpoint:

```bash
curl -s http://127.0.0.1:7860/healthz
curl -s http://127.0.0.1:7860/api/hosts | head -c 500
curl -s http://127.0.0.1:7860/api/models | head -c 500
curl -s http://127.0.0.1:7860/api/results
curl -s http://127.0.0.1:7860/api/runs
```

Expected: each returns 200 with reasonable JSON. `/api/hosts` should report unreachable=true for any runner that isn't actually running (with an error), and reachable=true with model lists for any that is. `/api/results` and `/api/runs` may be empty if you haven't migrated old JSONL.

- [ ] **Step 4: (Optional) Migrate existing perf.jsonl on drubuntu**

```bash
uv run llm-toolkit db migrate /home/drew/llm-toolkit/perf.jsonl \
    --host drubuntu --runner ollama --gpu 3080ti
```

Expected: prints `Imported N rows into ~/.local/share/llm-toolkit/results.db`. Then `curl /api/results` shows them.

- [ ] **Step 5: Commit any tweaks**

If the smoke test surfaces any small fixes, commit them now with conventional messages. Otherwise, no commit needed for this verification step.
