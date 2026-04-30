# Runner Dashboard — Phase 3: Run page + jobs + WebSocket

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Light up the Run page. After this phase a user can pick a suite + host/runner/gpu + model in the browser, hit "Run", and watch the existing CLI execute as a subprocess with stdout streaming live over a WebSocket. Resulting rows appear in `/api/results` tagged with the originating `run_id`. The "Run benchmark" button on Hosts cards now works (pre-fills the form), and Results rows that came from a UI-triggered run link back to their run/log.

**Architecture:** A single in-process asyncio worker (`llm_toolkit.jobs`) runs at most one job at a time. `POST /api/runs` inserts a `runs` row with `status='pending'` and enqueues the run; the worker pops the next pending run, sets it to `running`, shells out to `llm-toolkit bench-perf` or `llm-toolkit bench` as a subprocess, tees stdout into a per-run log file (`~/.local/share/llm-toolkit/runs/<id>.log`) and into an in-memory broadcaster. On exit it parses the JSONL the CLI produced, inserts each row into `results` tagged with `run_id` + host/runner/gpu, sets `status='success'|'failed'`, and emits a final `finished` event. `WS /ws/runs/{id}` first replays the on-disk log, then subscribes to the broadcaster — so a client that disconnects mid-run can reconnect and see everything. `DELETE /api/runs/{id}` cancels the subprocess (SIGTERM with a 5-second SIGKILL grace). The frontend Run page is a small form + a live-tail panel that consumes these endpoints. Job state lives only in SQLite + the on-disk log files; the in-memory broadcaster is purely for live fan-out.

**Tech Stack:** Existing — FastAPI 0.115, Python 3.12 asyncio (`asyncio.create_subprocess_exec`, `asyncio.Queue`), SQLite, Preact 10 + wouter-preact, Vitest. No new dependencies.

**Out of scope (deferred to v1.5+):** Multi-job concurrency (one job at a time, period), per-runner concurrency relaxation, log rotation/cleanup, retry-on-fail, suite-arg validation beyond the obvious required-field checks, chart of streaming throughput over time during a run, log download as a file (the path is shown so the user can `tail -f` it themselves if they want), and a "rerun this run" button on past run detail.

---

## File structure (Phase 3)

**New backend files:**

```
src/llm_toolkit/jobs/
  __init__.py           Public API: JobQueue, JobEvent
  events.py             Event dataclasses + JSON encoding
  worker.py             Subprocess runner + log/broadcast tee + result import
  queue.py              In-process asyncio queue with single-concurrency worker task
  broadcaster.py        Per-run-id pub/sub used by WebSocket handlers
  argv.py               Map a `runs` row to the CLI argv that runs it
```

**Modified backend files:**
- `src/llm_toolkit/web/deps.py` — `AppContext` gains `queue: JobQueue` and `runs_dir: Path`.
- `src/llm_toolkit/web/app.py` — register a FastAPI lifespan that starts/stops the worker; thread the new context fields through `make_context`.
- `src/llm_toolkit/web/routes/runs.py` — add `POST /api/runs`, `DELETE /api/runs/{id}`, `WS /ws/runs/{id}`.
- `src/llm_toolkit/db.py` — no schema changes (Phase 1 already created the `runs` table); just verify columns are still right.

**New backend tests:**
```
tests/jobs/
  __init__.py
  conftest.py           Shared fixtures (fake CLI script paths)
  test_argv.py
  test_broadcaster.py
  test_worker.py
  test_queue.py
tests/web/
  test_runs_post.py
  test_runs_cancel.py
  test_runs_ws.py
```

**New frontend files (all under `web/src/`):**
```
hooks/
  useRunWebSocket.ts    Connect to /ws/runs/<id>, expose log lines + status
pages/run/
  RunForm.tsx           Pickers + submit
  RunDetail.tsx         Live log tail + parsed-row count + cancel button
  SuiteArgs.tsx         Per-suite arg form (small, generated)
  suiteArgsSchema.ts    Pure data: which fields each suite shows
__tests__/
  useRunWebSocket.test.tsx
  RunForm.test.tsx
  SuiteArgs.test.tsx
  suiteArgsSchema.test.ts
```

**Modified frontend files:**
- `web/src/types.ts` — add `CreateRunRequest`, `CreateRunResponse`, `RunEvent`, suite-args helpers.
- `web/src/api.ts` — add `createRun`, `cancelRun`, `runWsUrl`.
- `web/src/pages/RunPage.tsx` — replace the placeholder with the real page.
- `web/src/components/Sidebar.tsx` — add a "Run" button next to each runner that pre-fills `/run?host=…&runner=…&gpu=…`.
- `web/src/pages/HostsPage.tsx` — same pre-fill button on each runner card.
- `web/src/pages/results/ResultsTable.tsx` — when `run_id` is set, the existing expanded row shows a `View run` link → `/run?id=<run_id>` (read-only mode).
- `web/vite.config.ts` — extend the dev proxy so `/ws` is also proxied to `:7860`.

---

## Task 1: Job event types

**Files:**
- Create: `src/llm_toolkit/jobs/events.py`
- Create: `src/llm_toolkit/jobs/__init__.py`
- Create: `tests/jobs/__init__.py`
- Create: `tests/jobs/conftest.py`

- [ ] **Step 1: Write the failing test for event JSON encoding**

Create `tests/jobs/conftest.py`:

```python
"""Shared fixtures for job tests."""
```

Create `tests/jobs/__init__.py` (empty file).

Create `tests/jobs/test_events.py`:

```python
import json

from llm_toolkit.jobs.events import JobEvent


def test_log_event_to_json():
    e = JobEvent.log("hello world")
    assert e.type == "log"
    assert e.to_json() == json.dumps({"type": "log", "line": "hello world"})


def test_status_event_to_json():
    e = JobEvent.status("running")
    assert e.to_json() == json.dumps({"type": "status", "status": "running"})


def test_finished_event_to_json():
    e = JobEvent.finished("success", exit_code=0, results_imported=12)
    payload = json.loads(e.to_json())
    assert payload == {
        "type": "finished",
        "status": "success",
        "exit_code": 0,
        "results_imported": 12,
    }


def test_result_event_to_json():
    e = JobEvent.result(result_id=42, benchmark="throughput_benchy",
                        model="qwen3:8b",
                        metrics={"tg_throughput": 73.4})
    payload = json.loads(e.to_json())
    assert payload["type"] == "result"
    assert payload["result_id"] == 42
    assert payload["metrics"]["tg_throughput"] == 73.4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/jobs/test_events.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'llm_toolkit.jobs'`.

- [ ] **Step 3: Implement events module**

Create `src/llm_toolkit/jobs/__init__.py`:

```python
"""In-process job runner.

Public API:
    JobQueue       — single-concurrency asyncio queue + worker task
    JobEvent       — log/status/result/finished events streamed to WS subscribers
    Broadcaster    — per-run-id pub/sub, used by the WS handlers
"""

from llm_toolkit.jobs.broadcaster import Broadcaster
from llm_toolkit.jobs.events import JobEvent
from llm_toolkit.jobs.queue import JobQueue

__all__ = ["Broadcaster", "JobEvent", "JobQueue"]
```

Create `src/llm_toolkit/jobs/events.py`:

```python
"""Events streamed from a running job to its WebSocket subscribers."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal


EventType = Literal["log", "status", "result", "finished"]


@dataclass(frozen=True)
class JobEvent:
    type: EventType
    payload: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def log(cls, line: str) -> "JobEvent":
        return cls("log", {"line": line})

    @classmethod
    def status(cls, status: str) -> "JobEvent":
        return cls("status", {"status": status})

    @classmethod
    def result(cls, *, result_id: int, benchmark: str, model: str,
               metrics: dict[str, Any]) -> "JobEvent":
        return cls("result", {
            "result_id": result_id,
            "benchmark": benchmark,
            "model": model,
            "metrics": metrics,
        })

    @classmethod
    def finished(cls, status: str, *, exit_code: int | None,
                 results_imported: int) -> "JobEvent":
        return cls("finished", {
            "status": status,
            "exit_code": exit_code,
            "results_imported": results_imported,
        })

    def to_json(self) -> str:
        return json.dumps({"type": self.type, **self.payload})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/jobs/test_events.py -v`
Expected: 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/llm_toolkit/jobs/__init__.py src/llm_toolkit/jobs/events.py \
        tests/jobs/__init__.py tests/jobs/conftest.py tests/jobs/test_events.py
git commit -m "feat(jobs): event types for run streaming"
```

---

## Task 2: argv builder

**Files:**
- Create: `src/llm_toolkit/jobs/argv.py`
- Create: `tests/jobs/test_argv.py`

The worker needs to translate a `runs` table row (suite, model, base_url, suite-specific args) into the exact argv it will spawn. Isolate that mapping so it's easy to test without touching subprocess code.

- [ ] **Step 1: Write the failing test**

Create `tests/jobs/test_argv.py`:

```python
from llm_toolkit.jobs.argv import build_argv


def test_perf_argv_minimal():
    argv = build_argv(
        benchmark="throughput_benchy",
        model="qwen3:8b",
        base_url="http://127.0.0.1:11434/v1",
        results_path="/tmp/run_42.jsonl",
        args={},
    )
    assert argv[:3] == ["llm-toolkit", "bench-perf", "--url"]
    assert "http://127.0.0.1:11434/v1" in argv
    assert "--models" in argv
    assert "qwen3:8b" in argv
    assert "--results" in argv
    assert "/tmp/run_42.jsonl" in argv
    assert "--benchmark-name" in argv
    assert "throughput_benchy" in argv


def test_perf_argv_with_suite_args():
    argv = build_argv(
        benchmark="throughput_benchy",
        model="qwen3:8b",
        base_url="http://127.0.0.1:11434/v1",
        results_path="/tmp/r.jsonl",
        args={"pp": [2048, 4096], "tg": [256], "concurrency": [1, 4],
              "tokenizer": "Qwen/Qwen3-8B"},
    )
    assert "--pp" in argv
    pp_idx = argv.index("--pp")
    assert argv[pp_idx + 1 : pp_idx + 3] == ["2048", "4096"]
    assert "--tokenizer" in argv
    assert "Qwen/Qwen3-8B" in argv


def test_accuracy_suite_argv():
    argv = build_argv(
        benchmark="context_scaling",
        model="qwen3:8b",
        base_url="http://127.0.0.1:11434",
        results_path="/tmp/r.db",
        args={},
    )
    assert argv[:2] == ["llm-toolkit", "bench"]
    assert "--suite" in argv and "context_scaling" in argv
    assert "--models" in argv and "qwen3:8b" in argv
    assert "--url" in argv and "http://127.0.0.1:11434" in argv


def test_unknown_benchmark_raises():
    import pytest
    with pytest.raises(ValueError, match="unknown benchmark"):
        build_argv(benchmark="not_a_suite", model="m",
                   base_url="x", results_path="y", args={})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/jobs/test_argv.py -v`
Expected: FAIL with import error.

- [ ] **Step 3: Implement argv builder**

Create `src/llm_toolkit/jobs/argv.py`:

```python
"""Translate a planned run into the CLI argv that executes it.

The web UI never re-implements benchmark logic — it just shells out to
the same `llm-toolkit` CLI a human would type. This module is the only
place that knows the mapping (benchmark → subcommand → flags).
"""

from __future__ import annotations

from typing import Any

PERF_BENCHMARKS = {"throughput_benchy"}
ACCURACY_BENCHMARKS = {"context_scaling", "classifier", "throughput", "coding"}


def build_argv(
    *,
    benchmark: str,
    model: str,
    base_url: str,
    results_path: str,
    args: dict[str, Any],
) -> list[str]:
    if benchmark in PERF_BENCHMARKS:
        return _perf_argv(model, base_url, results_path, args, benchmark=benchmark)
    if benchmark in ACCURACY_BENCHMARKS:
        return _accuracy_argv(benchmark, model, base_url, results_path, args)
    raise ValueError(f"unknown benchmark: {benchmark!r}")


def _perf_argv(
    model: str,
    base_url: str,
    results_path: str,
    args: dict[str, Any],
    *,
    benchmark: str,
) -> list[str]:
    argv: list[str] = [
        "llm-toolkit", "bench-perf",
        "--url", base_url,
        "--models", model,
        "--results", results_path,
        "--benchmark-name", benchmark,
    ]
    for key in ("pp", "tg", "depth", "concurrency"):
        v = args.get(key)
        if v:
            argv.append(f"--{key}")
            argv.extend(str(x) for x in v)
    if args.get("runs") is not None:
        argv += ["--runs", str(args["runs"])]
    if args.get("tokenizer"):
        argv += ["--tokenizer", args["tokenizer"]]
    if args.get("served_model_name"):
        argv += ["--served-model-name", args["served_model_name"]]
    if args.get("prefix_caching"):
        argv += ["--prefix-caching"]
    if args.get("no_cache"):
        argv += ["--no-cache"]
    if args.get("skip_coherence"):
        argv += ["--skip-coherence"]
    if args.get("no_warmup"):
        argv += ["--no-warmup"]
    return argv


def _accuracy_argv(
    benchmark: str, model: str, base_url: str,
    results_path: str, args: dict[str, Any],
) -> list[str]:
    argv = [
        "llm-toolkit", "bench",
        "--suite", benchmark,
        "--models", model,
        "--url", base_url,
        "--results", results_path,
    ]
    if args.get("provider"):
        argv += ["--provider", args["provider"]]
    return argv
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/jobs/test_argv.py -v`
Expected: 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/llm_toolkit/jobs/argv.py tests/jobs/test_argv.py
git commit -m "feat(jobs): build CLI argv from a planned run"
```

---

## Task 3: Broadcaster

**Files:**
- Create: `src/llm_toolkit/jobs/broadcaster.py`
- Create: `tests/jobs/test_broadcaster.py`

A `Broadcaster` is a per-run-id fan-out: the worker writes events to it, every WebSocket client subscribes and receives them. Subscribers that fall behind are dropped (they can reconnect and replay from the log file).

- [ ] **Step 1: Write the failing test**

Create `tests/jobs/test_broadcaster.py`:

```python
import asyncio

import pytest

from llm_toolkit.jobs.broadcaster import Broadcaster
from llm_toolkit.jobs.events import JobEvent


@pytest.mark.asyncio
async def test_subscriber_receives_published_events():
    bc = Broadcaster()
    sub = bc.subscribe()
    await bc.publish(JobEvent.log("hi"))
    e = await asyncio.wait_for(sub.get(), timeout=0.5)
    assert e.type == "log"
    assert e.payload["line"] == "hi"


@pytest.mark.asyncio
async def test_two_subscribers_both_receive():
    bc = Broadcaster()
    a, b = bc.subscribe(), bc.subscribe()
    await bc.publish(JobEvent.status("running"))
    ea = await asyncio.wait_for(a.get(), timeout=0.5)
    eb = await asyncio.wait_for(b.get(), timeout=0.5)
    assert ea.type == eb.type == "status"


@pytest.mark.asyncio
async def test_unsubscribe_stops_delivery():
    bc = Broadcaster()
    sub = bc.subscribe()
    bc.unsubscribe(sub)
    await bc.publish(JobEvent.log("ignored"))
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(sub.get(), timeout=0.05)


@pytest.mark.asyncio
async def test_close_signals_subscribers_with_none():
    bc = Broadcaster()
    sub = bc.subscribe()
    await bc.close()
    sentinel = await asyncio.wait_for(sub.get(), timeout=0.5)
    assert sentinel is None


@pytest.mark.asyncio
async def test_slow_subscriber_dropped_when_buffer_full():
    bc = Broadcaster(max_queue=2)
    sub = bc.subscribe()
    await bc.publish(JobEvent.log("a"))
    await bc.publish(JobEvent.log("b"))
    await bc.publish(JobEvent.log("c"))
    assert sub not in bc._subs  # noqa: SLF001
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/jobs/test_broadcaster.py -v`
Expected: FAIL with import error.

- [ ] **Step 3: Implement broadcaster**

Create `src/llm_toolkit/jobs/broadcaster.py`:

```python
"""Per-run-id event fan-out used by /ws/runs/<id> handlers."""

from __future__ import annotations

import asyncio
from typing import Optional

from llm_toolkit.jobs.events import JobEvent


class Broadcaster:
    def __init__(self, max_queue: int = 1024) -> None:
        self._subs: list[asyncio.Queue[Optional[JobEvent]]] = []
        self._max_queue = max_queue
        self._closed = False

    def subscribe(self) -> asyncio.Queue[Optional[JobEvent]]:
        q: asyncio.Queue[Optional[JobEvent]] = asyncio.Queue(self._max_queue)
        self._subs.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[Optional[JobEvent]]) -> None:
        try:
            self._subs.remove(q)
        except ValueError:
            pass

    async def publish(self, event: JobEvent) -> None:
        for q in list(self._subs):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                self.unsubscribe(q)

    async def close(self) -> None:
        self._closed = True
        for q in list(self._subs):
            try:
                q.put_nowait(None)
            except asyncio.QueueFull:
                self.unsubscribe(q)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/jobs/test_broadcaster.py -v`
Expected: 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/llm_toolkit/jobs/broadcaster.py tests/jobs/test_broadcaster.py
git commit -m "feat(jobs): per-run-id event broadcaster"
```

---

## Task 4: Worker subprocess + log tee + result import

**Files:**
- Create: `src/llm_toolkit/jobs/worker.py`
- Create: `tests/jobs/test_worker.py`

The worker is the core of Phase 3: it spawns the subprocess, tees stdout to a log file and a Broadcaster, watches for cancellation, and on exit imports the JSONL output as `results` rows tagged with the run's `host`/`runner`/`gpu`/`run_id`.

- [ ] **Step 1: Write the failing tests**

Create `tests/jobs/test_worker.py`:

```python
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


def _echo_argv(out_lines: list[str], jsonl_target: Path,
               jsonl_rows: list[dict] | None = None,
               exit_code: int = 0) -> list[str]:
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
        host="h", runner="ollama", gpu="3080ti", benchmark="throughput_benchy",
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
    rows = [{
        "benchmark": "throughput_benchy",
        "model": "qwen3:8b",
        "timestamp": time.time(),
        "metrics": {"tg_throughput": 73.4},
        "metadata": {"key": "row1"},
    }]
    spec = RunSpec(
        run_id=rid,
        argv=_echo_argv(["done"], results_path, jsonl_rows=rows),
        log_path=tmp_path / f"{rid}.log",
        results_path=results_path,
        host="h", runner="ollama", gpu="3080ti", benchmark="throughput_benchy",
    )

    await run_subprocess(spec, db_path=db, broadcaster=bc)

    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        run = conn.execute("SELECT * FROM runs WHERE id = ?", (rid,)).fetchone()
        results = list(conn.execute(
            "SELECT * FROM results WHERE run_id = ?", (rid,)))
    assert run["status"] == "success"
    assert run["exit_code"] == 0
    assert run["finished_at"] is not None
    assert len(results) == 1
    assert results[0]["host"] == "h"
    assert results[0]["runner"] == "ollama"
    assert results[0]["gpu"] == "3080ti"
    assert json.loads(results[0]["metrics"])["tg_throughput"] == 73.4


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
        host="h", runner="ollama", gpu="3080ti", benchmark="throughput_benchy",
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
    script = (
        "import time,sys\n"
        "while True:\n"
        "    print('tick', flush=True)\n"
        "    time.sleep(0.05)\n"
    )
    spec = RunSpec(
        run_id=rid,
        argv=[sys.executable, "-c", script],
        log_path=tmp_path / f"{rid}.log",
        results_path=results_path,
        host="h", runner="ollama", gpu="3080ti", benchmark="throughput_benchy",
    )

    task = asyncio.create_task(run_subprocess(spec, db_path=db, broadcaster=bc))
    await asyncio.sleep(0.2)
    spec.cancel_event.set()
    await asyncio.wait_for(task, timeout=10.0)

    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        run = conn.execute("SELECT * FROM runs WHERE id = ?", (rid,)).fetchone()
    assert run["status"] == "cancelled"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/jobs/test_worker.py -v`
Expected: FAIL with import error.

- [ ] **Step 3: Implement worker**

Create `src/llm_toolkit/jobs/worker.py`:

```python
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
import json
import signal
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path

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
            await broadcaster.publish(JobEvent.result(
                result_id=row["id"],
                benchmark=row["benchmark"],
                model=row["model"],
                metrics=row["metrics"],
            ))

        status = "success" if exit_code == 0 else "failed"
        _finalise(db_path, spec.run_id, status=status, exit_code=exit_code)
        await broadcaster.publish(
            JobEvent.finished(status, exit_code=exit_code, results_imported=len(imported))
        )
    except Exception as e:
        _finalise(db_path, spec.run_id, status="failed", exit_code=None, error=str(e))
        await broadcaster.publish(JobEvent.log(f"[worker] error: {e}"))
        await broadcaster.publish(
            JobEvent.finished("failed", exit_code=None, results_imported=0)
        )
    finally:
        log_fh.close()
        await broadcaster.close()


async def _stream_stdout(
    proc: asyncio.subprocess.Process,
    log_fh,
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
    except asyncio.TimeoutError:
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
    db: Path, run_id: int, *,
    status: str, exit_code: int | None, error: str | None = None,
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
                "UPDATE runs SET status = ?, exit_code = ?, finished_at = ? "
                "WHERE id = ?",
                (status, exit_code, time.time(), run_id),
            )
        conn.commit()


def _import_results(db: Path, spec: RunSpec) -> list[dict]:
    if not spec.results_path.exists():
        return []
    sink = SqliteResultStore(db)
    src = JsonlResultStore(spec.results_path)
    inserted: list[dict] = []
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
        inserted.append({
            "id": rid,
            "benchmark": r.benchmark,
            "model": r.model,
            "metrics": r.metrics,
        })
    return inserted
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/jobs/test_worker.py -v`
Expected: 4 tests pass (cancel test takes ~1s).

- [ ] **Step 5: Commit**

```bash
git add src/llm_toolkit/jobs/worker.py tests/jobs/test_worker.py
git commit -m "feat(jobs): subprocess worker with log tee + result import"
```

---

## Task 5: JobQueue (single-concurrency runner)

**Files:**
- Create: `src/llm_toolkit/jobs/queue.py`
- Create: `tests/jobs/test_queue.py`

The queue holds an `asyncio.Queue` of RunSpecs and a single worker task that drains it. It exposes `enqueue`, `cancel`, and `broadcaster_for` (look up the broadcaster for an active run, or `None` if it's already finished).

- [ ] **Step 1: Write the failing tests**

Create `tests/jobs/test_queue.py`:

```python
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
        host="h", runner="ollama", gpu="g", benchmark="throughput_benchy",
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
                rows = list(conn.execute(
                    "SELECT status FROM runs WHERE id IN (?, ?)", ids))
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
            argv=[sys.executable, "-c",
                  "import time\nwhile True:\n  print('.', flush=True); time.sleep(0.05)\n"],
            log_path=tmp_path / f"{rid}.log",
            results_path=tmp_path / f"{rid}.jsonl",
            host="h", runner="ollama", gpu="g", benchmark="throughput_benchy",
        )
        await q.enqueue(spec)
        await asyncio.sleep(0.3)
        assert q.cancel(rid) is True
        deadline = time.time() + 10.0
        while time.time() < deadline:
            with sqlite3.connect(db) as conn:
                row = conn.execute(
                    "SELECT status FROM runs WHERE id = ?", (rid,)
                ).fetchone()
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
        await q.enqueue(_echo_spec(rid, tmp_path, "hi"))
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/jobs/test_queue.py -v`
Expected: FAIL with import error.

- [ ] **Step 3: Implement queue**

Create `src/llm_toolkit/jobs/queue.py`:

```python
"""Single-concurrency in-process job queue.

One worker task drains an asyncio.Queue of RunSpecs. While a run is active,
its Broadcaster is registered in `_active` so WS handlers can find it.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from llm_toolkit.jobs.broadcaster import Broadcaster
from llm_toolkit.jobs.worker import RunSpec, run_subprocess


class JobQueue:
    def __init__(self, *, db_path: Path, runs_dir: Path) -> None:
        self._db_path = db_path
        self._runs_dir = runs_dir
        self._queue: asyncio.Queue[RunSpec] = asyncio.Queue()
        self._active: dict[int, tuple[RunSpec, Broadcaster]] = {}
        self._worker: asyncio.Task | None = None

    async def start(self) -> None:
        if self._worker is not None:
            return
        self._runs_dir.mkdir(parents=True, exist_ok=True)
        self._worker = asyncio.create_task(self._run_loop(), name="job-queue-worker")

    async def stop(self) -> None:
        if self._worker is None:
            return
        self._worker.cancel()
        try:
            await self._worker
        except asyncio.CancelledError:
            pass
        for spec, _bc in self._active.values():
            spec.cancel_event.set()
        self._worker = None

    async def enqueue(self, spec: RunSpec) -> None:
        await self._queue.put(spec)

    def cancel(self, run_id: int) -> bool:
        entry = self._active.get(run_id)
        if entry is None:
            return False
        spec, _bc = entry
        spec.cancel_event.set()
        return True

    def broadcaster_for(self, run_id: int) -> Broadcaster | None:
        entry = self._active.get(run_id)
        return entry[1] if entry else None

    async def _run_loop(self) -> None:
        while True:
            spec = await self._queue.get()
            bc = Broadcaster()
            self._active[spec.run_id] = (spec, bc)
            try:
                await run_subprocess(spec, db_path=self._db_path, broadcaster=bc)
            finally:
                self._active.pop(spec.run_id, None)
                self._queue.task_done()
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/jobs/test_queue.py -v`
Expected: 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/llm_toolkit/jobs/queue.py tests/jobs/test_queue.py
git commit -m "feat(jobs): single-concurrency queue with cancel + broadcaster lookup"
```

---

## Task 6: Wire JobQueue into AppContext + lifespan

**Files:**
- Modify: `src/llm_toolkit/web/deps.py`
- Modify: `src/llm_toolkit/web/app.py`
- Modify: `tests/web/test_app.py` (add a check for the new fields)

- [ ] **Step 1: Write the failing test**

Append to `tests/web/test_app.py`:

```python
def test_app_context_has_queue_and_runs_dir(tmp_path):
    from llm_toolkit.web.app import create_app
    app = create_app(db_path=tmp_path / "r.db", hosts_path=tmp_path / "h.toml",
                     runs_dir=tmp_path / "runs")
    ctx = app.state.ctx
    assert ctx.queue is not None
    assert ctx.runs_dir.exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/web/test_app.py::test_app_context_has_queue_and_runs_dir -v`
Expected: FAIL — `ctx` has no attribute `queue`.

- [ ] **Step 3: Replace `src/llm_toolkit/web/deps.py`**

```python
"""Dependency-injection helpers for FastAPI handlers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from llm_toolkit.discovery.cache import DiscoveryCache
from llm_toolkit.discovery.hosts import HostsConfig, load_hosts
from llm_toolkit.discovery.llama_server import LlamaServerAdapter
from llm_toolkit.discovery.ollama import OllamaAdapter
from llm_toolkit.discovery.types import RunnerAdapter
from llm_toolkit.discovery.vllm import VLLMAdapter
from llm_toolkit.jobs import JobQueue


DEFAULT_RUNS_DIR = Path(
    os.environ.get(
        "LLM_TOOLKIT_RUNS_DIR",
        str(Path.home() / ".local" / "share" / "llm-toolkit" / "runs"),
    )
)


@dataclass
class AppContext:
    db_path: Path
    hosts_path: Path
    runs_dir: Path
    cache: DiscoveryCache
    adapters: dict[str, RunnerAdapter]
    queue: JobQueue

    def hosts(self) -> HostsConfig:
        return load_hosts(self.hosts_path)


def make_context(
    db_path: Path,
    hosts_path: Path,
    runs_dir: Path = DEFAULT_RUNS_DIR,
) -> AppContext:
    runs_dir.mkdir(parents=True, exist_ok=True)
    return AppContext(
        db_path=db_path,
        hosts_path=hosts_path,
        runs_dir=runs_dir,
        cache=DiscoveryCache(db_path=db_path, ttl_s=10.0),
        adapters={
            "ollama": OllamaAdapter(),
            "vllm": VLLMAdapter(),
            "llama-server": LlamaServerAdapter(),
        },
        queue=JobQueue(db_path=db_path, runs_dir=runs_dir),
    )
```

- [ ] **Step 4: Replace `src/llm_toolkit/web/app.py` with lifespan support**

```python
"""FastAPI app factory."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import llm_toolkit
from llm_toolkit.db import DEFAULT_DB_PATH, init_db
from llm_toolkit.discovery.hosts import DEFAULT_HOSTS_PATH
from llm_toolkit.web.deps import DEFAULT_RUNS_DIR, make_context


def _resolve_web_dist() -> Path:
    return Path(llm_toolkit.__file__).resolve().parent.parent.parent / "web" / "dist"


def create_app(
    *,
    db_path: Path | str = DEFAULT_DB_PATH,
    hosts_path: Path | str = DEFAULT_HOSTS_PATH,
    runs_dir: Path | str = DEFAULT_RUNS_DIR,
) -> FastAPI:
    db = Path(db_path)
    hosts = Path(hosts_path)
    runs = Path(runs_dir)
    init_db(db)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await app.state.ctx.queue.start()
        try:
            yield
        finally:
            await app.state.ctx.queue.stop()

    app = FastAPI(title="llm-toolkit", lifespan=lifespan)
    app.state.ctx = make_context(db_path=db, hosts_path=hosts, runs_dir=runs)

    from llm_toolkit.web.routes import hosts as hosts_routes
    app.include_router(hosts_routes.router)

    from llm_toolkit.web.routes import results as results_routes
    app.include_router(results_routes.router)

    from llm_toolkit.web.routes import runs as runs_routes
    app.include_router(runs_routes.router)

    from llm_toolkit.web.routes import models as models_routes
    app.include_router(models_routes.router)

    @app.get("/healthz")
    def healthz() -> dict:
        return {"ok": True}

    dist = _resolve_web_dist()
    index_html = dist / "index.html"
    if index_html.exists():
        assets_dir = dist / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa_fallback(full_path: str) -> FileResponse:
            return FileResponse(index_html)

    return app
```

- [ ] **Step 5: Verify**

Run: `uv run pytest tests/web/test_app.py -v` then `uv run pytest -x`.
Expected: existing + new test pass; no regressions.

- [ ] **Step 6: Commit**

```bash
git add src/llm_toolkit/web/deps.py src/llm_toolkit/web/app.py tests/web/test_app.py
git commit -m "feat(web): wire JobQueue into AppContext via FastAPI lifespan"
```

---

## Task 7: POST /api/runs

**Files:**
- Modify: `src/llm_toolkit/web/routes/runs.py`
- Create: `tests/web/test_runs_post.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/web/test_runs_post.py`:

```python
"""Tests for POST /api/runs."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from llm_toolkit.db import init_db
from llm_toolkit.web.app import create_app


def _seed_snapshot(db: Path) -> None:
    init_db(db)
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO host_snapshots (host, runner, gpu, runner_version, "
            "timestamp, state) VALUES (?, ?, ?, ?, ?, ?)",
            ("drubuntu", "ollama", "3080ti", "0.5.7", time.time(), "{}"),
        )
        conn.commit()


def _client(tmp_path: Path) -> TestClient:
    db = tmp_path / "r.db"
    _seed_snapshot(db)
    app = create_app(db_path=db, hosts_path=tmp_path / "h.toml",
                     runs_dir=tmp_path / "runs")
    return TestClient(app)


def test_post_run_inserts_pending_row(tmp_path: Path):
    with patch("llm_toolkit.jobs.queue.JobQueue.enqueue", autospec=True):
        with _client(tmp_path) as client:
            r = client.post("/api/runs", json={
                "benchmark": "throughput_benchy",
                "model": "qwen3:8b",
                "host": "drubuntu",
                "runner": "ollama",
                "gpu": "3080ti",
                "base_url": "http://drubuntu:11434/v1",
                "args": {"pp": [2048], "tg": [256]},
            })
            assert r.status_code == 201, r.text
            body = r.json()
            assert isinstance(body["id"], int)
            assert body["status"] == "pending"

    db = tmp_path / "r.db"
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM runs WHERE id = ?", (body["id"],)
        ).fetchone()
    assert row["status"] == "pending"
    assert row["benchmark"] == "throughput_benchy"
    assert row["model"] == "qwen3:8b"
    assert row["host"] == "drubuntu"
    assert row["runner_version"] == "0.5.7"


def test_post_run_rejects_unknown_benchmark(tmp_path: Path):
    with _client(tmp_path) as client:
        r = client.post("/api/runs", json={
            "benchmark": "not-a-suite",
            "model": "qwen3:8b",
            "host": "drubuntu",
            "runner": "ollama",
            "gpu": "3080ti",
            "base_url": "http://drubuntu:11434/v1",
            "args": {},
        })
        assert r.status_code == 400


def test_post_run_requires_fields(tmp_path: Path):
    with _client(tmp_path) as client:
        r = client.post("/api/runs", json={"benchmark": "throughput_benchy"})
        assert r.status_code == 422
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/web/test_runs_post.py -v`
Expected: FAIL with 405 (Method Not Allowed) — POST endpoint doesn't exist yet.

- [ ] **Step 3: Replace `src/llm_toolkit/web/routes/runs.py`**

```python
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
            benchmark=body.benchmark, model=body.model,
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
            (body.benchmark, body.model, body.host, body.runner, body.gpu,
             runner_version, args_json, ""),
        )
        conn.commit()
        rid = cur.lastrowid
        log_path = ctx.runs_dir / f"{rid}.log"
        results_path = ctx.runs_dir / f"{rid}.jsonl"
        conn.execute("UPDATE runs SET log_path = ? WHERE id = ?",
                     (str(log_path), rid))
        conn.commit()

    argv = build_argv(
        benchmark=body.benchmark, model=body.model,
        base_url=body.base_url, results_path=str(results_path),
        args=body.args,
    )
    spec = RunSpec(
        run_id=rid, argv=argv, log_path=log_path, results_path=results_path,
        host=body.host, runner=body.runner, gpu=body.gpu, benchmark=body.benchmark,
    )
    await ctx.queue.enqueue(spec)
    return {"id": rid, "status": "pending"}
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/web/test_runs_post.py tests/web/test_runs_route.py -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/llm_toolkit/web/routes/runs.py tests/web/test_runs_post.py
git commit -m "feat(web): POST /api/runs enqueues a job"
```

---

## Task 8: DELETE /api/runs/{id} (cancel)

**Files:**
- Modify: `src/llm_toolkit/web/routes/runs.py`
- Create: `tests/web/test_runs_cancel.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/web/test_runs_cancel.py`:

```python
import sqlite3
import time
from pathlib import Path

from fastapi.testclient import TestClient

from llm_toolkit.db import init_db
from llm_toolkit.web.app import create_app


def _seed(db: Path, status: str = "running") -> int:
    init_db(db)
    with sqlite3.connect(db) as conn:
        cur = conn.execute(
            "INSERT INTO runs (status, benchmark, model, host, runner, gpu, "
            "args_json, started_at) VALUES (?, 'throughput_benchy', 'm', "
            "'h', 'ollama', 'g', '{}', ?)",
            (status, time.time()),
        )
        conn.commit()
        return cur.lastrowid


def test_cancel_unknown_run_returns_404(tmp_path: Path):
    db = tmp_path / "r.db"
    init_db(db)
    app = create_app(db_path=db, hosts_path=tmp_path / "h.toml",
                     runs_dir=tmp_path / "runs")
    with TestClient(app) as client:
        r = client.delete("/api/runs/9999")
        assert r.status_code == 404


def test_cancel_finished_run_409(tmp_path: Path):
    db = tmp_path / "r.db"
    rid = _seed(db, status="success")
    app = create_app(db_path=db, hosts_path=tmp_path / "h.toml",
                     runs_dir=tmp_path / "runs")
    with TestClient(app) as client:
        r = client.delete(f"/api/runs/{rid}")
        assert r.status_code == 409


def test_cancel_pending_or_running_signals_queue(tmp_path: Path):
    db = tmp_path / "r.db"
    rid = _seed(db, status="running")
    app = create_app(db_path=db, hosts_path=tmp_path / "h.toml",
                     runs_dir=tmp_path / "runs")
    called: list[int] = []
    with TestClient(app) as client:
        app.state.ctx.queue.cancel = lambda rid: (called.append(rid) or True)
        r = client.delete(f"/api/runs/{rid}")
        assert r.status_code == 200
        assert called == [rid]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/web/test_runs_cancel.py -v`
Expected: FAIL — DELETE not implemented yet (405).

- [ ] **Step 3: Append DELETE handler to `src/llm_toolkit/web/routes/runs.py`**

```python
@router.delete("/{rid}")
def cancel_run(rid: int, request: Request) -> dict:
    ctx = request.app.state.ctx
    with sqlite3.connect(ctx.db_path) as conn:
        row = conn.execute("SELECT status FROM runs WHERE id = ?", (rid,)).fetchone()
    if row is None:
        raise HTTPException(404, "run not found")
    status = row[0]
    if status not in {"pending", "running"}:
        raise HTTPException(409, f"cannot cancel a run in status {status!r}")
    ok = ctx.queue.cancel(rid)
    if not ok and status == "pending":
        with sqlite3.connect(ctx.db_path) as conn:
            conn.execute(
                "UPDATE runs SET status = 'cancelled', "
                "finished_at = strftime('%s','now') "
                "WHERE id = ? AND status = 'pending'",
                (rid,),
            )
            conn.commit()
    return {"id": rid, "cancelled": True}
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/web/test_runs_cancel.py -v`
Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/llm_toolkit/web/routes/runs.py tests/web/test_runs_cancel.py
git commit -m "feat(web): DELETE /api/runs/{id} cancels via the queue"
```

---

## Task 9: WS /ws/runs/{id} with replay

**Files:**
- Modify: `src/llm_toolkit/web/routes/runs.py`
- Modify: `src/llm_toolkit/web/app.py`
- Create: `tests/web/test_runs_ws.py`

When a client connects, first send any existing log lines from the on-disk file (replay). Then either subscribe to the live broadcaster (run still active) or send a final `finished` event reflecting the DB row and close.

- [ ] **Step 1: Write the failing tests**

Create `tests/web/test_runs_ws.py`:

```python
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
    with TestClient(app) as client:
        with client.websocket_connect("/ws/runs/1") as ws:
            messages = []
            try:
                while True:
                    messages.append(ws.receive_text())
            except Exception:
                pass
    types_seen = [json.loads(m)["type"] for m in messages]
    lines = [json.loads(m).get("line") for m in messages
             if json.loads(m)["type"] == "log"]
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
            r = client.post("/api/runs", json={
                "benchmark": "throughput_benchy", "model": "m",
                "host": "h", "runner": "ollama", "gpu": "g",
                "base_url": "http://h/v1", "args": {},
            })
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
    log_lines = [json.loads(m)["line"] for m in messages
                 if json.loads(m)["type"] == "log"]
    assert any(l.startswith("tick-") for l in log_lines)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/web/test_runs_ws.py -v`
Expected: FAIL — WS route doesn't exist (connect fails).

- [ ] **Step 3: Append the WS handler to `src/llm_toolkit/web/routes/runs.py`**

Append at the end of the file:

```python
from fastapi import WebSocket, WebSocketDisconnect

from llm_toolkit.jobs.events import JobEvent


def _terminal_event(row: sqlite3.Row) -> JobEvent:
    return JobEvent.finished(
        row["status"],
        exit_code=row["exit_code"],
        results_imported=0,
    )


async def runs_websocket_endpoint(websocket: WebSocket, rid: int) -> None:
    """Public entry — registered as `/ws/runs/{rid}` from app.py."""
    ctx = websocket.app.state.ctx
    await websocket.accept()
    with sqlite3.connect(ctx.db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (rid,)).fetchone()
    if row is None:
        await websocket.send_text(JobEvent.log(f"[error] run {rid} not found").to_json())
        await websocket.close()
        return

    log_path = Path(row["log_path"]) if row["log_path"] else None
    if log_path and log_path.exists():
        try:
            for line in log_path.read_text().splitlines():
                await websocket.send_text(JobEvent.log(line).to_json())
        except FileNotFoundError:
            pass

    bc = ctx.queue.broadcaster_for(rid)
    if bc is None:
        await websocket.send_text(_terminal_event(row).to_json())
        await websocket.close()
        return

    sub = bc.subscribe()
    try:
        while True:
            event = await sub.get()
            if event is None:
                break
            await websocket.send_text(event.to_json())
    except WebSocketDisconnect:
        pass
    finally:
        bc.unsubscribe(sub)
        try:
            await websocket.close()
        except Exception:
            pass
```

- [ ] **Step 4: Mount the WS route in `app.py`**

In `src/llm_toolkit/web/app.py`, immediately after `app.include_router(runs_routes.router)`, add:

```python
    from llm_toolkit.web.routes.runs import runs_websocket_endpoint
    app.add_api_websocket_route("/ws/runs/{rid}", runs_websocket_endpoint)
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/web/test_runs_ws.py -v`
Expected: 2 tests pass.

Run: `uv run pytest -x`
Expected: full suite passes.

- [ ] **Step 6: Commit**

```bash
git add src/llm_toolkit/web/routes/runs.py src/llm_toolkit/web/app.py \
        tests/web/test_runs_ws.py
git commit -m "feat(web): WS /ws/runs/{id} with on-disk replay + live broadcast"
```

---

## Task 10: Frontend types + api.ts updates + WS proxy

**Files:**
- Modify: `web/src/types.ts`
- Modify: `web/src/api.ts`
- Modify: `web/vite.config.ts`

- [ ] **Step 1: Append to `web/src/types.ts`**

```ts
export interface CreateRunRequest {
  benchmark: string
  model: string
  host: string
  runner: string
  gpu: string | null
  base_url: string
  args: Record<string, unknown>
}

export interface CreateRunResponse {
  id: number
  status: 'pending'
}

export type RunEvent =
  | { type: 'log'; line: string }
  | { type: 'status'; status: string }
  | { type: 'result'; result_id: number; benchmark: string; model: string;
      metrics: Record<string, number | string | null> }
  | { type: 'finished'; status: string; exit_code: number | null;
      results_imported: number }
```

- [ ] **Step 2: Replace `web/src/api.ts`**

```ts
import type {
  CompareResponse,
  CreateRunRequest,
  CreateRunResponse,
  HostsResponse,
  ModelsResponse,
  ResultRow,
  ResultsQuery,
  ResultsResponse,
  RunRow,
  RunsResponse,
} from './types'

async function getJson<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, init)
  if (!r.ok) {
    const body = await r.text().catch(() => '')
    throw new Error(`${r.status} ${r.statusText}: ${body || url}`)
  }
  return r.json() as Promise<T>
}

function qs(params: Record<string, string | number | undefined>): string {
  const usp = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== '') usp.set(k, String(v))
  }
  const s = usp.toString()
  return s ? `?${s}` : ''
}

export function runWsUrl(id: number): string {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${window.location.host}/ws/runs/${id}`
}

export function runHref(host: string, runner: string, gpu: string | null): string {
  const u = new URLSearchParams({ host, runner })
  if (gpu) u.set('gpu', gpu)
  return `/run?${u.toString()}`
}

export const api = {
  hosts: () => getJson<HostsResponse>('/api/hosts'),
  refreshHosts: () => getJson<HostsResponse>('/api/hosts/refresh', { method: 'POST' }),

  results: (q: ResultsQuery = {}) =>
    getJson<ResultsResponse>(`/api/results${qs(q as Record<string, string | number | undefined>)}`),
  result: (id: number) => getJson<ResultRow>(`/api/results/${id}`),
  compare: (ids: number[]) =>
    getJson<CompareResponse>('/api/results/compare', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ ids }),
    }),

  runs: (q: { status?: string; limit?: number; offset?: number } = {}) =>
    getJson<RunsResponse>(`/api/runs${qs(q)}`),
  run: (id: number) => getJson<RunRow>(`/api/runs/${id}`),
  createRun: (body: CreateRunRequest) =>
    getJson<CreateRunResponse>('/api/runs', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    }),
  cancelRun: (id: number) =>
    getJson<{ id: number; cancelled: boolean }>(`/api/runs/${id}`, { method: 'DELETE' }),

  models: () => getJson<ModelsResponse>('/api/models'),
}
```

- [ ] **Step 3: Add WS proxy to `web/vite.config.ts`**

Open `web/vite.config.ts` and locate the existing `server.proxy` block. Add a `/ws` entry alongside the existing `/api` entry. The relevant block should look like:

```ts
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:7860',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://127.0.0.1:7860',
        ws: true,
        changeOrigin: true,
      },
    },
  },
```

- [ ] **Step 4: Verify the frontend still builds**

Run: `cd web && npm run build && cd ..`
Expected: clean build, no TS errors.

- [ ] **Step 5: Commit**

```bash
git add web/src/types.ts web/src/api.ts web/vite.config.ts
git commit -m "feat(web): API client for runs (create/cancel/ws) + dev /ws proxy"
```

---

## Task 11: useRunWebSocket hook

**Files:**
- Create: `web/src/hooks/useRunWebSocket.ts`
- Create: `web/src/__tests__/useRunWebSocket.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `web/src/__tests__/useRunWebSocket.test.tsx`:

```tsx
import { act, renderHook } from '@testing-library/preact'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useRunWebSocket } from '../hooks/useRunWebSocket'

class MockWS {
  static instances: MockWS[] = []
  url: string
  onopen: ((ev: Event) => void) | null = null
  onmessage: ((ev: MessageEvent) => void) | null = null
  onclose: ((ev: CloseEvent) => void) | null = null
  onerror: ((ev: Event) => void) | null = null
  closed = false
  constructor(url: string) {
    this.url = url
    MockWS.instances.push(this)
  }
  close() {
    this.closed = true
    this.onclose?.(new CloseEvent('close'))
  }
  send() {}
}

beforeEach(() => {
  MockWS.instances = []
  ;(globalThis as any).WebSocket = MockWS
})
afterEach(() => {
  vi.restoreAllMocks()
})

describe('useRunWebSocket', () => {
  it('accumulates log lines and tracks last status', () => {
    const { result } = renderHook(() => useRunWebSocket(7))
    const ws = MockWS.instances[0]
    act(() => {
      ws.onopen?.(new Event('open'))
      ws.onmessage?.(new MessageEvent('message', {
        data: JSON.stringify({ type: 'status', status: 'running' }),
      }))
      ws.onmessage?.(new MessageEvent('message', {
        data: JSON.stringify({ type: 'log', line: 'hello' }),
      }))
      ws.onmessage?.(new MessageEvent('message', {
        data: JSON.stringify({ type: 'log', line: 'world' }),
      }))
    })
    expect(result.current.logs).toEqual(['hello', 'world'])
    expect(result.current.status).toBe('running')
  })

  it('records terminal status on finished event', () => {
    const { result } = renderHook(() => useRunWebSocket(7))
    const ws = MockWS.instances[0]
    act(() => {
      ws.onmessage?.(new MessageEvent('message', {
        data: JSON.stringify({
          type: 'finished', status: 'success',
          exit_code: 0, results_imported: 3,
        }),
      }))
    })
    expect(result.current.status).toBe('success')
    expect(result.current.resultsImported).toBe(3)
    expect(result.current.finished).toBe(true)
  })

  it('closes the socket on unmount', () => {
    const { unmount } = renderHook(() => useRunWebSocket(7))
    const ws = MockWS.instances[0]
    unmount()
    expect(ws.closed).toBe(true)
  })

  it('does not connect when id is null', () => {
    renderHook(() => useRunWebSocket(null))
    expect(MockWS.instances).toHaveLength(0)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npm test -- useRunWebSocket --run`
Expected: FAIL with module not found.

- [ ] **Step 3: Implement the hook**

Create `web/src/hooks/useRunWebSocket.ts`:

```ts
import { useEffect, useRef, useState } from 'preact/hooks'
import { runWsUrl } from '../api'
import type { RunEvent } from '../types'

export interface UseRunWebSocket {
  logs: string[]
  status: string | null
  finished: boolean
  resultsImported: number
  error: string | null
}

export function useRunWebSocket(id: number | null): UseRunWebSocket {
  const [logs, setLogs] = useState<string[]>([])
  const [status, setStatus] = useState<string | null>(null)
  const [finished, setFinished] = useState(false)
  const [resultsImported, setResultsImported] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    setLogs([])
    setStatus(null)
    setFinished(false)
    setResultsImported(0)
    setError(null)
    if (id == null) return

    const ws = new WebSocket(runWsUrl(id))
    wsRef.current = ws

    ws.onmessage = (ev: MessageEvent) => {
      let parsed: RunEvent
      try {
        parsed = JSON.parse(ev.data) as RunEvent
      } catch {
        return
      }
      if (parsed.type === 'log') {
        setLogs(prev => [...prev, parsed.line])
      } else if (parsed.type === 'status') {
        setStatus(parsed.status)
      } else if (parsed.type === 'finished') {
        setStatus(parsed.status)
        setResultsImported(parsed.results_imported)
        setFinished(true)
      }
    }
    ws.onerror = () => setError('WebSocket error')

    return () => {
      ws.close()
      wsRef.current = null
    }
  }, [id])

  return { logs, status, finished, resultsImported, error }
}
```

- [ ] **Step 4: Run tests**

Run: `cd web && npm test -- useRunWebSocket --run`
Expected: 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add web/src/hooks/useRunWebSocket.ts web/src/__tests__/useRunWebSocket.test.tsx
git commit -m "feat(web): useRunWebSocket hook for /ws/runs/<id>"
```

---

## Task 12: Suite-args schema + form

**Files:**
- Create: `web/src/pages/run/suiteArgsSchema.ts`
- Create: `web/src/pages/run/SuiteArgs.tsx`
- Create: `web/src/__tests__/suiteArgsSchema.test.ts`
- Create: `web/src/__tests__/SuiteArgs.test.tsx`

A small declarative schema drives the per-suite arg form and the API payload. Keeps the Run page free of giant if/else ladders.

- [ ] **Step 1: Write the failing tests**

Create `web/src/__tests__/suiteArgsSchema.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { argsForBenchmark, parseListField, SUITE_ARGS } from '../pages/run/suiteArgsSchema'

describe('suiteArgsSchema', () => {
  it('exposes throughput_benchy fields', () => {
    expect(argsForBenchmark('throughput_benchy').map(f => f.name))
      .toEqual(expect.arrayContaining(['pp', 'tg', 'concurrency', 'tokenizer']))
  })

  it('returns empty list for accuracy benchmarks', () => {
    expect(argsForBenchmark('context_scaling')).toEqual([])
  })

  it('parses list fields from comma-separated input', () => {
    expect(parseListField('2048, 4096')).toEqual([2048, 4096])
    expect(parseListField('')).toEqual(null)
    expect(parseListField('abc')).toEqual(null)
  })

  it('SUITE_ARGS keys match known benchmarks', () => {
    expect(Object.keys(SUITE_ARGS)).toEqual(
      expect.arrayContaining([
        'throughput_benchy', 'context_scaling', 'classifier', 'coding',
      ]),
    )
  })
})
```

Create `web/src/__tests__/SuiteArgs.test.tsx`:

```tsx
import { fireEvent, render, screen } from '@testing-library/preact'
import { describe, expect, it, vi } from 'vitest'
import { SuiteArgs } from '../pages/run/SuiteArgs'

describe('SuiteArgs', () => {
  it('renders fields for throughput_benchy', () => {
    render(<SuiteArgs benchmark="throughput_benchy" value={{}} onChange={() => {}} />)
    expect(screen.getByLabelText(/pp/i)).toBeTruthy()
    expect(screen.getByLabelText(/tg/i)).toBeTruthy()
    expect(screen.getByLabelText(/tokenizer/i)).toBeTruthy()
  })

  it('renders nothing for context_scaling', () => {
    const { container } = render(
      <SuiteArgs benchmark="context_scaling" value={{}} onChange={() => {}} />
    )
    expect(container.textContent).toContain('No extra arguments')
  })

  it('emits parsed list values', () => {
    const onChange = vi.fn()
    render(<SuiteArgs benchmark="throughput_benchy" value={{}} onChange={onChange} />)
    fireEvent.input(screen.getByLabelText(/pp/i), { target: { value: '2048,4096' } })
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ pp: [2048, 4096] }))
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd web && npm test -- suiteArgsSchema SuiteArgs --run`
Expected: FAIL with module not found.

- [ ] **Step 3: Implement schema**

Create `web/src/pages/run/suiteArgsSchema.ts`:

```ts
export type FieldKind = 'list-int' | 'string' | 'boolean' | 'int'

export interface SuiteArgField {
  name: string
  label: string
  kind: FieldKind
  placeholder?: string
  help?: string
}

export const SUITE_ARGS: Record<string, SuiteArgField[]> = {
  throughput_benchy: [
    { name: 'pp',  label: 'pp (prompt-processing tokens)',
      kind: 'list-int', placeholder: '2048, 4096' },
    { name: 'tg',  label: 'tg (generation tokens)',
      kind: 'list-int', placeholder: '128, 256' },
    { name: 'depth', label: 'depth',
      kind: 'list-int', placeholder: '0, 4096' },
    { name: 'concurrency', label: 'concurrency',
      kind: 'list-int', placeholder: '1, 4' },
    { name: 'runs', label: 'runs', kind: 'int', placeholder: '3' },
    { name: 'tokenizer', label: 'tokenizer (HF repo)',
      kind: 'string', placeholder: 'Qwen/Qwen3-8B' },
    { name: 'served_model_name', label: 'served-model-name',
      kind: 'string' },
    { name: 'prefix_caching', label: 'enable prefix caching', kind: 'boolean' },
    { name: 'no_cache',       label: 'no cache',              kind: 'boolean' },
    { name: 'skip_coherence', label: 'skip coherence check',  kind: 'boolean' },
    { name: 'no_warmup',      label: 'no warmup',             kind: 'boolean' },
  ],
  context_scaling: [],
  classifier: [],
  coding: [],
}

export function argsForBenchmark(benchmark: string): SuiteArgField[] {
  return SUITE_ARGS[benchmark] ?? []
}

export function parseListField(raw: string): number[] | null {
  const trimmed = raw.trim()
  if (!trimmed) return null
  const parts = trimmed.split(',').map(s => s.trim()).filter(Boolean)
  const nums = parts.map(p => Number(p))
  if (nums.some(n => Number.isNaN(n))) return null
  return nums
}
```

- [ ] **Step 4: Implement `SuiteArgs.tsx`**

Create `web/src/pages/run/SuiteArgs.tsx`:

```tsx
import { argsForBenchmark, parseListField, type SuiteArgField } from './suiteArgsSchema'

interface Props {
  benchmark: string
  value: Record<string, unknown>
  onChange: (next: Record<string, unknown>) => void
}

export function SuiteArgs({ benchmark, value, onChange }: Props) {
  const fields = argsForBenchmark(benchmark)
  if (fields.length === 0) {
    return <p class="text-text-muted text-sm">No extra arguments for this suite.</p>
  }
  function set(name: string, v: unknown) {
    const next = { ...value }
    if (v === undefined || v === null || v === '') {
      delete next[name]
    } else {
      next[name] = v
    }
    onChange(next)
  }
  return (
    <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
      {fields.map(f => (
        <FieldRow key={f.name} field={f} value={value[f.name]} onChange={v => set(f.name, v)} />
      ))}
    </div>
  )
}

function FieldRow({
  field, value, onChange,
}: { field: SuiteArgField; value: unknown; onChange: (v: unknown) => void }) {
  const id = `arg-${field.name}`
  if (field.kind === 'boolean') {
    return (
      <label class="flex items-center gap-2 text-sm">
        <input id={id} type="checkbox"
               checked={Boolean(value)}
               onChange={(e: any) => onChange(e.currentTarget.checked)} />
        {field.label}
      </label>
    )
  }
  return (
    <label class="flex flex-col gap-1 text-sm">
      <span>{field.label}</span>
      <input
        id={id}
        type="text"
        class="border rounded px-2 py-1 bg-bg-base"
        placeholder={field.placeholder}
        value={renderValue(value)}
        onInput={(e: any) => {
          const raw = e.currentTarget.value as string
          if (field.kind === 'list-int') onChange(parseListField(raw))
          else if (field.kind === 'int') {
            const n = Number(raw)
            onChange(raw === '' ? undefined : Number.isNaN(n) ? null : n)
          } else {
            onChange(raw === '' ? undefined : raw)
          }
        }}
      />
    </label>
  )
}

function renderValue(v: unknown): string {
  if (v == null) return ''
  if (Array.isArray(v)) return v.join(', ')
  return String(v)
}
```

- [ ] **Step 5: Run tests**

Run: `cd web && npm test -- suiteArgsSchema SuiteArgs --run`
Expected: 7 tests pass.

- [ ] **Step 6: Commit**

```bash
git add web/src/pages/run/suiteArgsSchema.ts web/src/pages/run/SuiteArgs.tsx \
        web/src/__tests__/suiteArgsSchema.test.ts web/src/__tests__/SuiteArgs.test.tsx
git commit -m "feat(web): suite-args schema + small generated form"
```

---

## Task 13: RunForm — pickers + submit

**Files:**
- Create: `web/src/pages/run/RunForm.tsx`
- Create: `web/src/__tests__/RunForm.test.tsx`

The form pulls hosts/runners/models from `/api/hosts`, narrows by user selection, and POSTs `/api/runs` on submit.

- [ ] **Step 1: Write the failing tests**

Create `web/src/__tests__/RunForm.test.tsx`:

```tsx
import { fireEvent, render, screen, waitFor } from '@testing-library/preact'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { RunForm } from '../pages/run/RunForm'
import * as apiModule from '../api'

const HOSTS = {
  hosts: [{
    name: 'localhost',
    runners: [{
      runner: 'ollama',
      base_url: 'http://127.0.0.1:11434',
      gpu: 'm3-max',
      version: '0.5.7',
      reachable: true, error: null,
      installed_models: [{ tag: 'qwen3:8b', size_bytes: null, modified: null }],
      loaded_models: [],
      raw: {},
    }],
  }],
}

beforeEach(() => {
  vi.spyOn(apiModule.api, 'hosts').mockResolvedValue(HOSTS as any)
})
afterEach(() => vi.restoreAllMocks())

describe('RunForm', () => {
  it('lets the user submit a valid run', async () => {
    const createRun = vi.spyOn(apiModule.api, 'createRun')
      .mockResolvedValue({ id: 11, status: 'pending' } as any)
    const onCreated = vi.fn()
    render(<RunForm onCreated={onCreated} initial={null} />)
    await waitFor(() => screen.getByText(/qwen3:8b/i))
    fireEvent.click(screen.getByRole('button', { name: /run/i }))
    await waitFor(() => expect(createRun).toHaveBeenCalled())
    const arg = createRun.mock.calls[0][0]
    expect(arg.benchmark).toBe('throughput_benchy')
    expect(arg.host).toBe('localhost')
    expect(arg.runner).toBe('ollama')
    expect(arg.model).toBe('qwen3:8b')
    expect(arg.base_url).toContain('11434')
    await waitFor(() => expect(onCreated).toHaveBeenCalledWith(11))
  })

  it('honours initial pre-fill', async () => {
    render(<RunForm onCreated={() => {}}
      initial={{ host: 'localhost', runner: 'ollama', gpu: 'm3-max' }} />)
    await waitFor(() => screen.getByText(/qwen3:8b/i))
    expect((screen.getByLabelText(/host/i) as HTMLSelectElement).value).toBe('localhost')
  })

  it('disables submit while a request is in flight', async () => {
    let resolve!: (v: any) => void
    vi.spyOn(apiModule.api, 'createRun').mockImplementation(
      () => new Promise(r => { resolve = r }) as any,
    )
    render(<RunForm onCreated={() => {}} initial={null} />)
    await waitFor(() => screen.getByText(/qwen3:8b/i))
    fireEvent.click(screen.getByRole('button', { name: /run/i }))
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /running…|run/i })
        .hasAttribute('disabled')).toBe(true))
    resolve({ id: 1, status: 'pending' })
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npm test -- RunForm --run`
Expected: FAIL — RunForm doesn't exist.

- [ ] **Step 3: Implement `RunForm.tsx`**

Create `web/src/pages/run/RunForm.tsx`:

```tsx
import { useEffect, useMemo, useState } from 'preact/hooks'
import { api } from '../../api'
import type { HostsResponse, ModelInfo } from '../../types'
import { SuiteArgs } from './SuiteArgs'

const BENCHMARKS = [
  'throughput_benchy', 'context_scaling', 'classifier', 'coding',
] as const

export interface RunFormPrefill {
  host?: string
  runner?: string
  gpu?: string | null
  model?: string
  benchmark?: string
}

interface Props {
  onCreated: (runId: number) => void
  initial: RunFormPrefill | null
  disabled?: boolean
}

export function RunForm({ onCreated, initial, disabled }: Props) {
  const [hosts, setHosts] = useState<HostsResponse | null>(null)
  const [benchmark, setBenchmark] = useState<string>(initial?.benchmark ?? 'throughput_benchy')
  const [host, setHost] = useState<string>(initial?.host ?? '')
  const [runner, setRunner] = useState<string>(initial?.runner ?? '')
  const [gpu, setGpu] = useState<string | null>(initial?.gpu ?? null)
  const [model, setModel] = useState<string>(initial?.model ?? '')
  const [args, setArgs] = useState<Record<string, unknown>>({})
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => { void api.hosts().then(setHosts).catch(e => setError(String(e))) }, [])

  const selectedHost = useMemo(
    () => hosts?.hosts.find(h => h.name === host) ?? null, [hosts, host])
  const runners = selectedHost?.runners ?? []
  const selectedRunner = useMemo(
    () => runners.find(r => r.runner === runner && (gpu == null || r.gpu === gpu)) ?? null,
    [runners, runner, gpu])
  const models: ModelInfo[] = selectedRunner?.installed_models ?? []

  useEffect(() => {
    if (!hosts) return
    if (!host && hosts.hosts[0]) setHost(hosts.hosts[0].name)
  }, [hosts, host])
  useEffect(() => {
    if (!runner && runners[0]) {
      setRunner(runners[0].runner)
      setGpu(runners[0].gpu ?? null)
    }
  }, [runner, runners])
  useEffect(() => {
    if (!model && models[0]) setModel(models[0].tag)
  }, [model, models])

  async function submit() {
    if (!selectedRunner) return
    setSubmitting(true)
    setError(null)
    try {
      const resp = await api.createRun({
        benchmark, model, host, runner,
        gpu: selectedRunner.gpu,
        base_url: selectedRunner.base_url,
        args,
      })
      onCreated(resp.id)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setSubmitting(false)
    }
  }

  const hostNames = hosts?.hosts.map(h => h.name) ?? []
  return (
    <form class="space-y-4" onSubmit={(e: any) => { e.preventDefault(); void submit() }}>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
        <Field label="Suite">
          <select value={benchmark} class="border rounded px-2 py-1 bg-bg-base"
                  onChange={(e: any) => setBenchmark(e.currentTarget.value)}>
            {BENCHMARKS.map(b => <option key={b} value={b}>{b}</option>)}
          </select>
        </Field>
        <Field label="Host">
          <select value={host} class="border rounded px-2 py-1 bg-bg-base"
                  onChange={(e: any) => {
                    setHost(e.currentTarget.value); setRunner(''); setGpu(null); setModel('')
                  }}>
            {hostNames.map(n => <option key={n} value={n}>{n}</option>)}
          </select>
        </Field>
        <Field label="Runner">
          <select value={`${runner}|${gpu ?? ''}`} class="border rounded px-2 py-1 bg-bg-base"
                  onChange={(e: any) => {
                    const [rt, g] = String(e.currentTarget.value).split('|')
                    setRunner(rt); setGpu(g || null); setModel('')
                  }}>
            {runners.map(r => (
              <option key={`${r.runner}|${r.gpu ?? ''}`}
                      value={`${r.runner}|${r.gpu ?? ''}`}>
                {r.runner}{r.gpu ? ` · ${r.gpu}` : ''}
                {r.reachable ? '' : ' (unreachable)'}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Model">
          <select value={model} class="border rounded px-2 py-1 bg-bg-base"
                  onChange={(e: any) => setModel(e.currentTarget.value)}>
            {models.map(m => <option key={m.tag} value={m.tag}>{m.tag}</option>)}
          </select>
        </Field>
      </div>

      <div>
        <h3 class="text-sm font-semibold mb-2">Suite arguments</h3>
        <SuiteArgs benchmark={benchmark} value={args} onChange={setArgs} />
      </div>

      {error && <div class="text-red-600 text-sm">{error}</div>}

      <button
        type="submit"
        class="bg-blue-600 text-white px-4 py-2 rounded disabled:opacity-50"
        disabled={disabled || submitting || !host || !runner || !model}
      >
        {submitting ? 'Running…' : 'Run'}
      </button>
    </form>
  )
}

function Field({ label, children }: { label: string; children: any }) {
  return (
    <label class="flex flex-col gap-1 text-sm">
      <span class="text-text-muted">{label}</span>
      {children}
    </label>
  )
}
```

- [ ] **Step 4: Run tests**

Run: `cd web && npm test -- RunForm --run`
Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add web/src/pages/run/RunForm.tsx web/src/__tests__/RunForm.test.tsx
git commit -m "feat(web): RunForm pickers + submit"
```

---

## Task 14: RunDetail — live tail + cancel

**Files:**
- Create: `web/src/pages/run/RunDetail.tsx`

A panel showing: status badge, last 500 log lines (auto-scroll to bottom), parsed-result count, cancel button while pending/running, "View results" link when finished.

- [ ] **Step 1: Implement `RunDetail.tsx`**

Create `web/src/pages/run/RunDetail.tsx`:

```tsx
import { useEffect, useRef } from 'preact/hooks'
import { Link } from 'wouter-preact'
import { api } from '../../api'
import { useRunWebSocket } from '../../hooks/useRunWebSocket'

const TAIL_LIMIT = 500

interface Props {
  runId: number
  onCleared: () => void
}

export function RunDetail({ runId, onCleared }: Props) {
  const { logs, status, finished, resultsImported, error } = useRunWebSocket(runId)
  const preRef = useRef<HTMLPreElement | null>(null)

  useEffect(() => {
    const el = preRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [logs])

  const visible = logs.length > TAIL_LIMIT ? logs.slice(-TAIL_LIMIT) : logs
  const cancelable = !finished && (status === 'pending' || status === 'running' || status == null)

  async function cancel() {
    try { await api.cancelRun(runId) } catch { /* WS will report */ }
  }

  return (
    <section class="border rounded p-3 space-y-3">
      <header class="flex items-center justify-between">
        <div class="flex items-center gap-3">
          <h2 class="text-lg font-semibold">Run #{runId}</h2>
          <StatusBadge status={status} />
          {resultsImported > 0 && (
            <span class="text-text-muted text-sm">
              {resultsImported} result{resultsImported === 1 ? '' : 's'} imported
            </span>
          )}
        </div>
        <div class="flex items-center gap-2">
          {cancelable && (
            <button class="text-sm border rounded px-2 py-1" onClick={cancel}>
              Cancel
            </button>
          )}
          {finished && (
            <Link href={`/?run_id=${runId}`} class="text-sm text-blue-600 hover:underline">
              View results
            </Link>
          )}
          <button class="text-sm text-text-muted hover:underline" onClick={onCleared}>
            Close
          </button>
        </div>
      </header>

      {error && <div class="text-red-600 text-sm">{error}</div>}

      <pre
        ref={preRef}
        class="bg-bg-elevated border rounded p-2 text-xs font-mono whitespace-pre-wrap
               max-h-96 overflow-auto"
      >{visible.join('\n')}</pre>
    </section>
  )
}

function StatusBadge({ status }: { status: string | null }) {
  const colour = status === 'success' ? 'bg-green-600'
    : status === 'failed' ? 'bg-red-600'
    : status === 'cancelled' ? 'bg-yellow-600'
    : 'bg-blue-600'
  return (
    <span class={`text-xs uppercase tracking-wide text-white px-2 py-0.5 rounded ${colour}`}>
      {status ?? 'connecting'}
    </span>
  )
}
```

- [ ] **Step 2: Verify build**

Run: `cd web && npm run build && cd ..`
Expected: clean build.

- [ ] **Step 3: Commit**

```bash
git add web/src/pages/run/RunDetail.tsx
git commit -m "feat(web): RunDetail live tail + cancel button"
```

---

## Task 15: RunPage — wire RunForm + RunDetail + URL pre-fill

**Files:**
- Modify: `web/src/pages/RunPage.tsx`

URL params drive pre-fill: `/run?host=…&runner=…&gpu=…&benchmark=…&model=…&id=<existing>`. When `id` is present we skip the form and jump straight to RunDetail.

- [ ] **Step 1: Replace `web/src/pages/RunPage.tsx`**

```tsx
import { useEffect, useState } from 'preact/hooks'
import { useLocation } from 'wouter-preact'
import { RunDetail } from './run/RunDetail'
import { RunForm, type RunFormPrefill } from './run/RunForm'

function parseQuery(search: string): URLSearchParams {
  return new URLSearchParams(search)
}

export function RunPage() {
  const [location] = useLocation()
  const search = typeof window !== 'undefined' ? window.location.search : ''
  const params = parseQuery(search)
  const idParam = params.get('id')
  const [activeId, setActiveId] = useState<number | null>(
    idParam ? Number(idParam) : null,
  )
  const [prefill] = useState<RunFormPrefill | null>(() => {
    const host = params.get('host')
    const runner = params.get('runner')
    const gpu = params.get('gpu')
    const model = params.get('model')
    const benchmark = params.get('benchmark')
    if (!host && !runner && !model && !benchmark) return null
    return {
      host: host ?? undefined,
      runner: runner ?? undefined,
      gpu: gpu,
      model: model ?? undefined,
      benchmark: benchmark ?? undefined,
    }
  })

  useEffect(() => {
    if (idParam) setActiveId(Number(idParam))
  }, [location, idParam])

  return (
    <div class="p-6 space-y-6 max-w-3xl">
      <h1 class="text-xl font-semibold">Run a benchmark</h1>
      {activeId == null ? (
        <RunForm onCreated={setActiveId} initial={prefill} />
      ) : (
        <RunDetail runId={activeId} onCleared={() => setActiveId(null)} />
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify build + tests**

Run: `cd web && npm run build && npm test -- --run && cd ..`
Expected: clean build, all frontend tests pass.

- [ ] **Step 3: Commit**

```bash
git add web/src/pages/RunPage.tsx
git commit -m "feat(web): wire RunForm + RunDetail into Run page (with URL pre-fill)"
```

---

## Task 16: Pre-fill links from Sidebar + Hosts cards

**Files:**
- Modify: `web/src/components/Sidebar.tsx`
- Modify: `web/src/pages/HostsPage.tsx`

Each runner row gets a small "Run" link that navigates to `/run?host=…&runner=…&gpu=…`. Reuses RunPage's pre-fill behaviour from the previous task. The shared `runHref` helper was added to `web/src/api.ts` in Task 10.

- [ ] **Step 1: Read the existing components**

Run:
```bash
cat web/src/components/Sidebar.tsx
cat web/src/pages/HostsPage.tsx
```

Identify where each runner is rendered:
- In Sidebar.tsx: a row containing `RunnerStatusDot`, the runner name, and the GPU label.
- In HostsPage.tsx: a card body that lists each runner snapshot.

- [ ] **Step 2: Add the `Run` link to Sidebar**

In `web/src/components/Sidebar.tsx`, add these imports near the top (alongside existing imports):

```ts
import { Link } from 'wouter-preact'
import { runHref } from '../api'
```

Inside the JSX where each runner row is rendered (look for the loop over `host.runners`), append the link to the right of the existing label. Insert this as the last child of the runner-row element:

```tsx
{r.reachable && (
  <Link href={runHref(host.name, r.runner, r.gpu)}
        class="ml-auto text-xs text-blue-600 hover:underline">
    Run
  </Link>
)}
```

(Where `r` is the iteration variable for the runner snapshot and `host.name` is the host name.)

- [ ] **Step 3: Add the `Run benchmark` link to HostsPage**

In `web/src/pages/HostsPage.tsx`, add the same imports:

```ts
import { Link } from 'wouter-preact'
import { runHref } from '../api'
```

Inside each runner-card section (where the existing JSX renders version, GPU, loaded/installed models), add at the bottom of that card:

```tsx
{r.reachable && (
  <Link href={runHref(host.name, r.runner, r.gpu)}
        class="text-sm text-blue-600 hover:underline">
    Run benchmark →
  </Link>
)}
```

- [ ] **Step 4: Verify**

Run: `cd web && npm run build && npm test -- --run && cd ..`
Expected: clean build, no test regressions.

Smoke-test by hand:
```bash
uv run llm-toolkit ui --port 7860 &
# Open http://127.0.0.1:7860/, click "Run" on a runner.
# The Run page opens with the host/runner/gpu fields pre-filled.
```
Stop the server when done.

- [ ] **Step 5: Commit**

```bash
git add web/src/components/Sidebar.tsx web/src/pages/HostsPage.tsx
git commit -m "feat(web): 'Run' shortcut links on Sidebar and Hosts cards"
```

---

## Task 17: Results row — link to originating run

**Files:**
- Modify: `web/src/pages/results/ResultsTable.tsx`

The expanded row (Phase 2) already shows raw metrics. When `run_id` is non-null on a result row, add a link to `/run?id=<run_id>`.

- [ ] **Step 1: Inspect the existing expanded-row JSX**

Run:
```bash
grep -n "run_id\|expanded\|raw metrics" web/src/pages/results/ResultsTable.tsx
```

Identify where the expanded row's JSX block lives.

- [ ] **Step 2: Add `Link` import if needed**

At the top of `web/src/pages/results/ResultsTable.tsx`, ensure:

```ts
import { Link } from 'wouter-preact'
```

is present. If it isn't already imported, add it.

- [ ] **Step 3: Add the link**

Inside the expanded-row JSX, near the existing raw-metrics block, add:

```tsx
{row.run_id != null && (
  <div class="mt-2 text-sm">
    <Link href={`/run?id=${row.run_id}`} class="text-blue-600 hover:underline">
      View run #{row.run_id}
    </Link>
  </div>
)}
```

(Where `row` is the variable holding the current `ResultRow` in scope.)

- [ ] **Step 4: Verify**

Run: `cd web && npm run build && npm test -- --run && cd ..`
Expected: clean build, no test regressions.

- [ ] **Step 5: Commit**

```bash
git add web/src/pages/results/ResultsTable.tsx
git commit -m "feat(web): link Results rows back to their originating run"
```

---

## Task 18: End-to-end smoke test + handoff doc

**Files:**
- Modify: `docs/superpowers/HANDOFF.md`

- [ ] **Step 1: Manual smoke test (with a real Ollama running locally)**

Terminal A:
```bash
uv run llm-toolkit ui --port 7860
```

Terminal B (browser):
1. Open http://127.0.0.1:7860/run
2. Pick `throughput_benchy` / `localhost` / `ollama` / `m3-max` / `qwen3:8b`
3. Add args: `pp = 2048`, `tg = 128`, `runs = 1`, `tokenizer = Qwen/Qwen3-8B`
4. Click `Run`. Watch log lines stream in; status flips to `success`; "View results" link appears.
5. Click "View results"; the new row is on the Results page.
6. Expand the new row; "View run #N" link sends you back to RunDetail.
7. Trigger another run, then click `Cancel` while it's in `running`; status flips to `cancelled`.

If everything works, proceed.

- [ ] **Step 2: Replace `docs/superpowers/HANDOFF.md`**

```markdown
# Runner Dashboard — Handoff

**Status as of <today's date>:** Phases 1, 2, and 3 are complete and on `main`. The web UI at `llm-toolkit ui` is feature-complete for v1: hosts/runners discovery, results browser with compare drawer, runs page with live WebSocket streaming, and cross-page navigation via `run_id`.

## Where we are

- **Spec** (locked): [`specs/2026-04-28-runner-dashboard-design.md`](specs/2026-04-28-runner-dashboard-design.md)
- **Phase 1 plan** (executed): [`plans/2026-04-28-runner-dashboard-phase1.md`](plans/2026-04-28-runner-dashboard-phase1.md)
- **Phase 2 plan** (executed): [`plans/2026-04-29-runner-dashboard-phase2.md`](plans/2026-04-29-runner-dashboard-phase2.md)
- **Phase 3 plan** (executed): [`plans/2026-04-29-runner-dashboard-phase3.md`](plans/2026-04-29-runner-dashboard-phase3.md)

## Try it

```bash
mkdir -p ~/.config/llm-toolkit
cat > ~/.config/llm-toolkit/hosts.toml <<'EOF'
[[host]]
name = "localhost"
[[host.runner]]
type = "ollama"
url  = "http://127.0.0.1:11434"
gpu  = "m3-max"
EOF

uv sync --extra dev --extra web
cd web && npm install && npm run build && cd ..
uv run llm-toolkit ui --port 7860
# open http://127.0.0.1:7860
```

## Operational notes

- Run logs live at `~/.local/share/llm-toolkit/runs/<id>.log` (override via `LLM_TOOLKIT_RUNS_DIR`).
- A run that's mid-flight survives WebSocket disconnects: reconnecting to `/ws/runs/<id>` replays the on-disk log and resumes live streaming.
- Single-concurrency is enforced inside the FastAPI process — submitting a second run while one is active queues it. There is no UI for queue depth in v1.

## Possible v1.5 / v2 work

- One-job-per-(host, runner, gpu) concurrency relaxation.
- Auto-rotate / TTL on `runs/<id>.log`.
- "Rerun this run" button on completed runs.
- Streaming throughput chart (rather than just text log) during a run.
```

Replace `<today's date>` with the actual date when committing.

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/HANDOFF.md
git commit -m "docs: handoff after Phase 3"
```

---

## Self-review checklist

- [ ] Every spec section in `specs/2026-04-28-runner-dashboard-design.md` covered:
  - Job runner ✓ (tasks 1–6)
  - POST /api/runs / DELETE /api/runs / WS /ws/runs ✓ (tasks 7–9)
  - Subprocess spawn + stdout streaming + log file ✓ (task 4)
  - Result import tagged with run_id/host/runner/gpu ✓ (task 4)
  - Cancel with SIGTERM grace ✓ (tasks 4, 8)
  - Run page form + suite-specific args + live tail ✓ (tasks 11–15)
  - Hosts "Run benchmark" button ✓ (task 16)
  - Results row link to run ✓ (task 17)
  - WS disconnect/replay ✓ (task 9)
  - Snapshot-based runner_version capture ✓ (task 7)
- [ ] No "TBD" / "implement later" / "etc." placeholders.
- [ ] Type names consistent across tasks (`RunSpec`, `JobEvent`, `Broadcaster`, `JobQueue`, `runs_websocket_endpoint`, `runHref`, `useRunWebSocket`, `RunForm`, `RunDetail`, `SuiteArgs`, `argsForBenchmark`).
- [ ] Every code-changing step shows the actual code.
- [ ] Test commands always specify expected outcome.
