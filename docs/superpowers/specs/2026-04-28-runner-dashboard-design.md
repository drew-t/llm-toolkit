# Runner Dashboard — Design Spec

**Status:** Approved for planning
**Date:** 2026-04-28
**Scope:** llm-toolkit web UI v1 — runner/model discovery + benchmark viewer + bench triggering
**Out of scope (deferred):** cross-runner orchestrator, model pull/delete management

## Goals

1. Answer "what runners and models are running on which hosts/GPUs right now?" without SSH.
2. Browse, sort, filter, and compare past benchmark results across host × runner × GPU × model.
3. Trigger benchmarks from the UI and watch them run live.

The flagship use case: comparing the same model running on different runners (e.g. Ollama vs llama-server) or different GPUs (3080ti vs 1060ti) on the same physical host.

## Non-goals (v1)

- Pulling, deleting, or swapping models on a runner.
- Multi-job orchestration matrices ("run this benchmark across every runner × every model").
- Auth — server binds `127.0.0.1` only.
- Distributed agents on remote hosts. The UI server polls remote runner HTTP APIs directly; no agent code on drubuntu.

## Architecture

```
┌────────────────────────────────────────────────────────┐
│  Browser (Preact + Vite + Tailwind v4 + TS)            │
│  Pages: Results | Hosts | Run | Models                 │
└─────────────────┬──────────────────────────────────────┘
                  │ REST + WebSocket
┌─────────────────┴──────────────────────────────────────┐
│  llm_toolkit.web   FastAPI server                      │
│  REST   /api/hosts /api/results /api/runs /api/models  │
│  WS     /ws/runs/<id>  (live stdout + result rows)     │
│  Static-serves built Vite assets at /                  │
├────────────────────────────────────────────────────────┤
│  llm_toolkit.discovery                                 │
│  RunnerAdapter Protocol                                │
│  OllamaAdapter, VLLMAdapter, LlamaServerAdapter        │
│  HostsConfig — TOML loader                             │
├────────────────────────────────────────────────────────┤
│  llm_toolkit.jobs                                      │
│  In-process asyncio queue (single-concurrency v1)      │
│  Spawns existing CLI as subprocess; tails stdout to WS │
├────────────────────────────────────────────────────────┤
│  llm_toolkit.db                                        │
│  SQLite (WAL), three tables: results / runs /          │
│  host_snapshots                                        │
└────────────────────────────────────────────────────────┘
```

**Process model.** One Python process — `llm-toolkit ui` — starts FastAPI on `127.0.0.1:7860` (configurable via `--port` and `--host`). FastAPI serves the prebuilt Vite assets from `web/dist/`. In dev, Vite's dev server runs separately on `:5173` and proxies `/api` and `/ws` to FastAPI.

**Where it runs.** Anywhere — the user's Mac polling drubuntu over LAN, or installed on drubuntu and reached over LAN. Same binary, same config.

**Repo layout.**

```
src/llm_toolkit/
  web/             FastAPI app + REST/WS handlers + static-asset wiring
  discovery/       Adapter Protocol + Ollama/vLLM/llama-server impls
  jobs/            Subprocess job runner + WS bridge
  db.py            SQLite schema, connection helper, JSONL importer
web/               Vite project (Preact + TS + Tailwind v4)
docs/superpowers/specs/   Design specs (this file)
```

CLI gains two new subcommands:

- `llm-toolkit ui` — starts the web server.
- `llm-toolkit db migrate <jsonl>...` — one-shot import of legacy JSONL files into SQLite. Accepts `--host` and `--runner` flags to backfill those columns.

Existing `bench` and `bench-perf` subcommands remain. They continue to write through `ResultStore`, which gains a SQLite backend (default) while keeping the JSONL writer available for back-compat in tests.

## Data model

SQLite database at `~/.local/share/llm-toolkit/results.db` (override via `LLM_TOOLKIT_DB` or `--db`). WAL mode for concurrent reads while jobs are writing.

```sql
CREATE TABLE results (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  benchmark   TEXT NOT NULL,
  model       TEXT NOT NULL,
  host        TEXT,
  runner      TEXT,                     -- 'ollama' | 'vllm' | 'llama-server'
  gpu         TEXT,                     -- user-set label, e.g. '3080ti'
  run_id      INTEGER REFERENCES runs(id),
  timestamp   REAL NOT NULL,
  metrics     TEXT NOT NULL,            -- JSON
  metadata    TEXT NOT NULL             -- JSON
);

CREATE TABLE runs (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  status          TEXT NOT NULL,        -- pending|running|success|failed|cancelled
  benchmark       TEXT NOT NULL,
  model           TEXT NOT NULL,
  host            TEXT,
  runner          TEXT,
  gpu             TEXT,
  runner_version  TEXT,                 -- captured at run start
  args_json       TEXT NOT NULL,        -- the bench-perf CLI args used
  config_json     TEXT,                 -- env vars, harness config, runner flags
  started_at      REAL,
  finished_at     REAL,
  exit_code       INTEGER,
  log_path        TEXT                  -- captured stdout/stderr file
);

CREATE TABLE host_snapshots (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  host            TEXT NOT NULL,
  runner          TEXT NOT NULL,
  gpu             TEXT,
  runner_version  TEXT,
  timestamp       REAL NOT NULL,
  state           TEXT NOT NULL,        -- JSON: installed/loaded models + raw runner extras
  config_json     TEXT                  -- launch flags for the runner itself
);

CREATE INDEX idx_results_bench_model ON results(benchmark, model);
CREATE INDEX idx_results_timestamp   ON results(timestamp);
CREATE INDEX idx_results_host_runner ON results(host, runner);
CREATE INDEX idx_results_host_gpu    ON results(host, gpu);
CREATE INDEX idx_snapshots_host_ts   ON host_snapshots(host, timestamp);
```

**JSON-as-TEXT** for `metrics`, `metadata`, `state`, `config_json`, `args_json`. SQLite's JSON1 functions (`json_extract`, `->`, `->>`) handle queries. `JSONB` is Postgres-only.

**Migration path.**
1. New install creates the DB on first run.
2. `llm-toolkit db migrate path1.jsonl path2.jsonl --host drubuntu --runner ollama --gpu 3080ti` reads JSONL files and inserts into `results` with the supplied backfill columns. Repeatable for batches with different hosts/runners.
3. Older JSONL data without per-row host/runner/gpu info gets the user-provided values; if not provided, those columns stay null.

**Storage class change.** `ResultStore` gets a SQLite-backed implementation that becomes the default. Its `.append()` API is unchanged — callers don't notice. The existing JSONL implementation stays in the codebase for the migration tool and for tests that prefer simple file fixtures.

## Discovery layer

Each runner gets an adapter implementing a small Protocol:

```python
@dataclass
class ModelInfo:
    tag: str
    size_bytes: int | None
    modified: float | None  # epoch

@dataclass
class LoadedModel:
    tag: str
    vram_bytes: int | None
    expires_at: float | None

@dataclass
class RunnerSnapshot:
    runner: str           # 'ollama' | 'vllm' | 'llama-server'
    base_url: str
    gpu: str | None       # from hosts.toml
    version: str | None
    reachable: bool
    error: str | None
    installed_models: list[ModelInfo]
    loaded_models: list[LoadedModel]
    raw: dict             # runner-specific extras (slots, /metrics, props)

class RunnerAdapter(Protocol):
    name: str
    async def probe(self, base_url: str) -> RunnerSnapshot: ...
```

**Adapters (v1 trio).**

- **OllamaAdapter** — uses `/api/version` (version), `/api/tags` (installed), `/api/ps` (loaded with VRAM/expires). All three combined into a single snapshot.
- **VLLMAdapter** — uses `/version` (version), `/v1/models` (served model — vLLM serves one model per process, so installed == loaded). Best-effort `/metrics` parse for KV-cache utilization stored in `raw`.
- **LlamaServerAdapter** — uses `/props` (version via `build_info`, ctx-size and other launch params into `config_json`), `/v1/models` (served model), `/slots` (current sequence load) into `raw`.

GPU label is user-set in `hosts.toml`. Auto-detected GPU info (e.g. llama-server `/props.system_info.CUDA0`) goes into `state` for reference but does **not** override the label. The label is the source of truth for grouping.

**Hosts config** at `~/.config/llm-toolkit/hosts.toml`:

```toml
[[host]]
name = "drubuntu"

[[host.runner]]
type = "ollama"
url  = "http://drubuntu:11434"
gpu  = "3080ti"

[[host.runner]]
type = "ollama"
url  = "http://drubuntu:11435"        # second ollama process pinned to other GPU
gpu  = "1060ti"

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
```

**Polling cadence.** On-demand only. Fetching `/api/hosts` triggers fresh probes for any (host, runner) snapshot older than 10 seconds. A "Refresh" button in the UI forces re-probe regardless of cache age. Every successful probe writes a `host_snapshots` row.

**Failure mode.** Unreachable runners return a snapshot with `reachable=False, error=<message>`. The UI shows them as red dots in the sidebar; the Hosts card shows the error. No retries beyond the request timeout (3s).

## Job runner

Triggering a benchmark from the Run page:

1. POST `/api/runs` with `{benchmark, host, runner, gpu, model, args}` → server inserts `runs` row with `status='pending'`, captures the resolved runner version from the latest `host_snapshots`, and returns the new `run_id`.
2. The browser opens `WS /ws/runs/<id>` and waits for streamed events.
3. The async worker (single-concurrency queue inside the FastAPI process) picks up the pending run and:
   - Sets `status='running'`, `started_at=now()`.
   - Shells out to the existing CLI: `llm-toolkit bench-perf --url <runner-url> --models <model> --benchmark-name <suite> --results /tmp/run_<id>.jsonl <args...>` for perf, or `llm-toolkit bench --suite <suite> --models <model> ...` for accuracy suites.
   - Streams stdout line-by-line to the WebSocket and appends to `log_path` (`~/.local/share/llm-toolkit/runs/<id>.log`).
4. On exit, parses the resulting JSONL (which the existing CLI already produces) into `results` rows tagged with `run_id`, `host`, `runner`, `gpu`. Sets `status='success'` (exit 0) or `status='failed'` (non-zero) and `finished_at=now()`. Pushes a final `{type:'finished'}` event to the WS.
5. On disconnect, the run continues. Reconnecting to `/ws/runs/<id>` replays the log from `log_path` then resumes live stream.

**Concurrency.** One job at a time. Running two benchmarks against the same GPU is meaningless; even cross-runner-on-same-GPU contends. v1.5 may relax to "one job per (host, runner, gpu)."

**Cancel.** DELETE `/api/runs/<id>` sets `status='cancelled'` and sends SIGTERM to the subprocess. SIGKILL after a 5s grace period.

## REST + WebSocket API

```
GET   /api/hosts                  → all hosts with snapshots (10s cache)
POST  /api/hosts/refresh          → force re-probe all hosts
GET   /api/hosts/{name}/runners/{runner}  → single runner snapshot

GET   /api/results                → list with filters (host, runner, gpu, model,
                                    benchmark, since, sort, order, limit, offset)
GET   /api/results/{id}           → single result with full metrics+metadata
POST  /api/results/compare        → body: {ids: [...]} → comparison summary

GET   /api/runs                   → list runs (status filter, limit, offset)
GET   /api/runs/{id}              → run detail + log path
POST  /api/runs                   → enqueue a new run
DELETE /api/runs/{id}             → cancel
WS    /ws/runs/{id}               → live stdout + result events

GET   /api/models                 → flat cross-host model index
```

## Pages (UI)

**Sidebar** (persistent): page links + collapsible host status. Each host shows a green/red dot per runner (reachable / not), with the runner name and GPU label.

**Results** *(default page)*. Sortable filterable table over the `results` table. Filter chips above the table; columns: ☑, benchmark, model, host/runner/gpu (combined cell), primary metric (auto-picked per suite — `tg_throughput` for perf, `score` for accuracy suites), secondary metric (e.g. `pp_throughput` when applicable), runner version, relative time, row menu. Default sort: `timestamp DESC`. Color: best-in-set green, worst-in-set red. Row click expands inline (raw metrics blob, link to `runs` row + log). Multi-select reveals a sticky "N selected → Compare" bar that opens the Compare drawer (per-selection cards with diff vs first row, plus a bar chart of the headline metric).

**Hosts**. Grid of host cards. Each card lists its runners (reachable status, version), GPU labels, currently loaded models with VRAM/expiry, and installed-but-not-loaded models below a fold. Per-runner "Run benchmark" button pre-fills the Run form.

**Run**. Form: suite (dropdown including `throughput_benchy`, `context_scaling`, `classifier`, `coding`), host (from config), runner (filtered to that host), gpu (filtered to that runner), model (auto-populated from the latest snapshot of that runner), suite-specific args (via a small generated form per suite). Submit → opens a Run Detail panel below the form with live tail of stdout and a streaming row count of parsed results. "Cancel" button while running.

**Models**. Flat cross-host model index — one row per (model_tag, host, runner, gpu, status). Click a row → Results page filtered to that model. The smallest page; mostly an index/lookup tool.

## Frontend

Preact + Vite + Tailwind v4 + TypeScript, mirroring the existing `~/projects/tmnt/web` stack.

- TanStack Table via `preact/compat` for the Results table (sort, filter, multi-select).
- WebSocket (not SSE) for the run stream — events carry structured payloads (parsed result rows + status transitions), not just log text.
- Charts: a small Preact-friendly bar/line component (Chart.js with `preact/compat`, or hand-rolled SVG — the Compare view only needs simple bars).
- No router library needed for v1 — four routes via `wouter` (tiny preact-compatible router).

`npm run build` outputs to `web/dist/`. FastAPI mounts `web/dist/` at `/` and falls back to `index.html` for client-side routes.

## Error handling

- Discovery probe failures: snapshot returned with `reachable=False, error=<message>`. Surfaces as a red dot + error tooltip in the sidebar; full error visible in the Hosts card. Failed probes still write `host_snapshots` rows so we have a record of the outage.
- Run failures: `runs.status='failed'`, `exit_code` captured, full log retained at `log_path`. Result rows from a partial run (already-flushed JSONL) are still imported and tagged with `run_id`. The UI shows a red banner with the last 20 lines of stderr.
- Database failures: an in-flight run that fails to write its results to SQLite leaves `runs.status='failed'` and surfaces a clear error to the WS client. The user can re-run; we do not auto-retry.
- WebSocket disconnect mid-run: the run continues. Reconnection replays the log from `log_path` and resumes live stream. Frontend shows a "reconnecting..." banner.

## Testing

- **Adapters**: each adapter has a unit test that mocks the runner's HTTP responses (using `respx` or `httpx.MockTransport`) and asserts the resulting `RunnerSnapshot`. One fixture per runner covering: success, version-only-no-models, partial-success-with-some-bad-data, total unreachable.
- **Discovery cache**: a unit test for the 10s cache behaviour.
- **DB migrations**: a test that creates a fresh DB, runs `db migrate` on a sample JSONL fixture, and asserts row counts + backfill columns.
- **Job runner**: a test that uses a fake CLI (an echo script) as the subprocess target and asserts that stdout is captured to `log_path`, results are imported, and `runs` ends in `success`. A second test for the SIGTERM-on-cancel path.
- **REST/WS**: FastAPI's `TestClient` for handlers; a small integration test that spins up the full app against a mocked discovery layer and asserts the round-trip from `/api/runs` POST → WS message stream → final `/api/results` row.
- **Frontend**: Vitest + a couple of component-level tests for the Results table sort/filter behaviour. No e2e in v1.

## Open questions for the implementation plan

These are intentional flexibility points for the implementer:

- Whether `wouter` or another tiny preact router is used. Pick what works.
- Whether the bar chart is hand-rolled SVG or a tiny library — the Compare drawer is the only place charts appear in v1.
- Whether `respx` or `httpx.MockTransport` is the test mocking style — pick whichever matches existing tests in the repo.
