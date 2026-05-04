# Architecture Deepening Plan

Date: 2026-05-02
Branch: `refactor/architecture-deepening`
Vocabulary: see `~/.claude-upkeep/skills/improve-codebase-architecture/LANGUAGE.md` (module / interface / depth / seam / adapter / leverage / locality).

## Goal

Five deepening refactors, in sequence, each landed as its own commit. Existing pytest suite is the safety net. New behavior gets new tests TDD-style; pure code-motion piggybacks on existing tests.

## Constraints

- **Internal-only treatment.** No deprecation shims. Rename/move freely except where TMNT (`~/projects/tmnt/benchmarking/context_scaling/bench.py`) imports from `llm_toolkit`. TMNT-touching surface: `bench.runner.run_suite`, `bench.runner.print_suite_result`, `bench.runner.suite_results_to_bench_results`, `bench.context.context_scaling_suite`, `providers.ollama.OllamaProvider`, `results.ResultStore`. These names must keep working with their current call shapes; bodies free to change.
- **Phase 3 dashboard work is landed** (per `git log`). Refactoring `discovery/cache.py` is OK now; #4 still goes last to keep the bench-side refactors isolated from cross-package churn.
- **Pre-step (commit on `main`):** commit the agent-skills setup files (`CLAUDE.md` change + `docs/agents/`) before branching, so the refactor branch starts clean.

## Stage 0 — preliminaries

- Commit agent-skills setup on `main`:
  - `CLAUDE.md` (existing diff)
  - `docs/agents/issue-tracker.md`
  - `docs/agents/triage-labels.md`
  - `docs/agents/domain.md`
- Create branch `refactor/architecture-deepening` from `main`.
- All subsequent stages land as commits on this branch.

## Stage 1 — `Scorer` module (candidate #4)

**Why first:** smallest blast radius (touches `bench/`); produces a clean test surface that Stage 2 reuses.

**Friction today:**
- Score precedence (`TestCase.score_fn` > `Suite.default_score_fn`) is implicit and lives inside `run_suite` (`bench/runner.py:72-73`).
- `optimize/prompt.py:118-121` reaches in to recompute averages over case results.
- `bench/classifier.py` ships `exact_match_scorer` as ad-hoc free function with no shared shape.

**What deepens:** new module `bench/scorer.py` with:
- `Scorer` Protocol — `score(text: str, expected: str) -> float`
- `resolve_scorer(case, suite) -> Scorer | None` — encodes precedence in one place
- `aggregate(scores: Iterable[float | None]) -> float | None` — used by both runner and optimize

**TDD targets (new tests in `tests/test_scorer.py`):**
- precedence: case scorer wins over suite scorer
- precedence: suite scorer used when case scorer absent
- precedence: returns None when neither set
- aggregation: ignores None and error scores
- aggregation: returns None when no scored cases
- `exact_match_scorer` satisfies the protocol

**Refactor:**
- `bench/runner.py:run_suite` — replace inline scorer resolution with `resolve_scorer`.
- `optimize/prompt.py:_evaluate` — replace ad-hoc averaging with `aggregate` + `resolve_scorer`.
- `bench/classifier.py:exact_match_scorer` — move to `bench/scorer.py` (stays exported from `bench` for callers).

**Tests touched:**
- `tests/test_runner.py` — should keep passing unchanged.
- `tests/test_optimizer.py` — should keep passing unchanged.
- New `tests/test_scorer.py`.

**Acceptance:** `uv run pytest` green; ruff clean.

## Stage 2 — Unified measurement module (candidates #1 + #6)

**Why second:** uses Scorer from Stage 1; subsumes #6 by making measurement a parameter, not a control-flow choice.

**Friction today:**
- `harness.run_warm_isolated` (warmup, nonce, repetitions, median) and `bench.runner.run_suite` (case iteration, scoring) solve overlapping problems with non-composable interfaces.
- `optimize/prompt.py` evaluates candidates without warmup or repetition → noisy convergence.

**What deepens:** new module `bench/measure.py` exposing `measure(provider, model, suite, *, strategy)` where `strategy` is one of:
- `Direct()` — current `run_suite` behavior (one pass per case, scoring on, no nonce, no warmup). Default.
- `WarmStable(warmup=True, repetitions=N, nonce=False)` — runs each case repetitions times after warmup, returns median metrics + scored response.
- `PerfIsolated(warmup=True, repetitions=N, nonce=True)` — current `run_warm_isolated` semantics, lifted to suite level.

Returned value: `SuiteResult` (existing dataclass; gains optional `repetitions` and `raw_runs` fields per case for stable strategies).

**Compat shim:**
- `bench.runner.run_suite(provider, model, suite, *, strip_think=True)` keeps working — body becomes `await measure(provider, model, suite, strategy=Direct(strip_think=strip_think))`.
- `harness.run_warm_isolated` deleted (no callers in repo or TMNT).
- `harness.make_nonce`, `harness.nonce_prompt`, `harness.median_metrics` move to `bench/measure.py` as private helpers (no callers depend on them).

**TDD targets (`tests/test_measure.py`):**
- `Direct` strategy: matches current `run_suite` output for a fake provider
- `WarmStable`: provider called `repetitions+1` times per case (warmup + reps)
- `WarmStable`: median is computed from per-rep metrics, not just the last
- `PerfIsolated`: each rep prompt is unique (nonce applied)
- error path: case error → CaseResult.error set, score=0.0, other reps not attempted
- scoring: uses Stage 1's `resolve_scorer`, applied to last/representative response

**Refactor:**
- `bench/measure.py` — new module.
- `bench/runner.py:run_suite` — thin shim → `measure(strategy=Direct())`.
- `harness.py` — deleted; old tests under `tests/test_harness.py` either delete or rewrite as `test_measure.py` cases (they exercise nonce + median, both still tested via `PerfIsolated`).
- `optimize/prompt.py:_evaluate` — switch to `measure(strategy=WarmStable(repetitions=3))` so candidate scoring is denoised. Add `OptimizeConfig.measurement_repetitions: int = 3` for tunability.
- `bench/throughput.py` — if it uses `run_warm_isolated`, switch to `measure(strategy=PerfIsolated(...))`.

**Tests touched:**
- `tests/test_harness.py` → renamed to `test_measure.py` (or deleted in favor of new tests).
- `tests/test_runner.py` — passes through the shim, should still be green.
- `tests/test_optimizer.py` — may need a fake provider that survives 3x more calls per case; update fixtures.

**Acceptance:** `uv run pytest` green; ruff clean. Manual smoke: `uv run llm-toolkit bench --suite throughput --models qwen3.5:9b` still produces a result.

## Stage 3 — `ResultStore` honesty (candidate #2)

**Why third:** independent of Stages 1–2, but small enough to slot in cleanly before the discovery refactor.

**Friction today:**
- `ResultStore(path)` is a polymorphic factory; `summary_table` lives only on JSONL; `query` is O(n) on JSONL vs indexed on SQLite. Callers can't reason about which they got.
- TMNT writes to `results.jsonl` via `ResultStore(path).append()` — that path must keep working.

**What deepens:**
- `JsonlResultStore` — narrow to `append()` only. Drop `_load`, `query`, `summary_table` from the class.
- `SqliteResultStore` — full interface: `append`, `query`, `summary_table`.
- New `ResultWriter` Protocol: just `append(result: BenchResult) -> None`. Factory `ResultStore(path)` is typed as `-> ResultWriter`.
- Module-level `_read_jsonl(path: Path) -> Iterable[BenchResult]` — private helper used by the `db migrate` CLI.

**TDD targets (`tests/test_results.py` updates + `tests/test_results_sqlite.py`):**
- `ResultWriter` protocol satisfied by both backends
- `JsonlResultStore` no longer has `query` (assert AttributeError or that it's not in the public surface)
- `SqliteResultStore.summary_table` produces same shape as the old JSONL version did
- Factory returns concrete types as expected by extension

**Refactor:**
- `results.py` — restructure as above.
- `bench/runner.py:_run_db_command` — read JSONL via `_read_jsonl`, not via `JsonlResultStore.query`.
- Any other internal caller of `JsonlResultStore.query` or `.summary_table` — hunt down via grep, redirect to SQLite or to `_read_jsonl`.
- TMNT untouched: `ResultStore(jsonl_path).append()` still works.

**Tests touched:**
- `tests/test_results.py` — drop tests asserting JSONL `query`/`summary_table`; replace with `_read_jsonl` tests where relevant.
- `tests/test_results_sqlite.py` — add `summary_table` tests.
- `tests/test_db_migrate_cli.py` — should still pass (uses migrator path).

**Acceptance:** `uv run pytest` green; ruff clean. Manual smoke: `uv run llm-toolkit db migrate <some.jsonl>` succeeds.

## Stage 4 — Split `DiscoveryCache` (candidate #3)

**Why fourth:** highest cross-package surface; keep it isolated from Stages 1–3 so a regression here can be reverted without unwinding the bench refactors.

**Friction today:**
- `DiscoveryCache.get` does TTL caching, calls `probe`, then synchronously writes `host_snapshots` from inside `async def`. Two concerns fused; `_persist` failure invisible to cache hits; `sqlite3.connect` in async path blocks the event loop.

**What deepens:**
- `discovery/cache.py` — pure in-memory TTL cache. Interface: `get(key, factory)`, `invalidate(key=None)`. No DB, no I/O.
- `discovery/snapshot_journal.py` — new module. Append-only writer to `host_snapshots`. Async-aware (uses a thread executor or `asyncio.to_thread` for the sqlite call). Interface: `append(host, snap) -> Awaitable[None]`.
- The discovery layer (`discovery/hosts.py` or wherever the probe pipeline lives) composes them: probe → cache.put → journal.append. Journal failures are observable (logged + caller can assert).

**TDD targets (`tests/discovery/test_cache.py` updates + `tests/discovery/test_snapshot_journal.py`):**
- Cache: TTL hit/miss, invalidation, no I/O regardless of factory result
- Journal: appends row to `host_snapshots`, fails loudly on bad path
- Composition: cache-hit short-circuits journal write
- Composition: journal failure does not corrupt cache state

**Refactor:**
- Split `discovery/cache.py`.
- New `discovery/snapshot_journal.py`.
- Update probe call sites in `discovery/{ollama,vllm,llama_server}.py` and/or `discovery/hosts.py` to compose cache + journal.
- `web/deps.py` — wire whichever new objects are needed at the FastAPI layer.

**Tests touched:**
- `tests/discovery/test_cache.py` — split: TTL tests stay; persistence tests move to new file.
- New `tests/discovery/test_snapshot_journal.py`.
- `tests/web/...` — adjust fixtures if the deps shape changes.

**Acceptance:** `uv run pytest` green; ruff clean. Manual smoke: `uv run llm-toolkit ui` starts; hosts page renders; refresh repopulates cache without log errors.

## Stage 5 — Coding-task trace (candidate #5)

**Why last:** TMNT touch — needs cross-repo coordination. Keep the change small enough to land in this branch and update TMNT's `pi_runner` in the same effort, but the TMNT update lands as a commit in TMNT, not here.

**Friction today:**
- `verify(work_dir)` only sees the filesystem; can't inspect tool calls, prompts, or partial outputs the executor saw.
- TMNT's `pi_runner.parse_agent_end` already extracts a structured event log — the data exists, the seam just doesn't carry it.

**What deepens:**
- New types in `bench/coding.py`:
  ```
  @dataclass class ToolCallEvent: name: str; input: dict; output: Any; timestamp: float
  @dataclass class TraceEvent: kind: str; payload: dict; timestamp: float
  ```
  (Final shape TBD by what TMNT's `pi_runner` already produces; mirror that.)
- `CodingResult` gains `trace: list[TraceEvent] = field(default_factory=list)`.
- `verify` signature becomes `Callable[[Path, CodingResult], VerifyResult]`. Existing verifiers that ignore the result work fine after a one-line param addition.

**TDD targets (`tests/test_coding.py` updates):**
- Executor populates `trace`; verify can read it
- `verify` can fail on a tool-call pattern in the trace, not just filesystem state
- Backwards: a verifier that ignores the trace still works

**Refactor:**
- `bench/coding.py` — types + signature change.
- `tests/test_coding.py` — add fake executor that yields a trace.

**TMNT-side companion (separate commit in `~/projects/tmnt`):**
- Update `pi_runner.run_pi_task` to populate `trace` from the agent_end event's message log.
- Update any TMNT verifiers that want to use trace data.

**Acceptance:** `uv run pytest` green; ruff clean. TMNT companion commit prepared (separate branch in TMNT, not merged with this PR).

## Final steps

- Push branch.
- Open PR titled `refactor: architecture deepening (5 stages)` with the staged commits visible.
- Note in the PR description that TMNT's `pi_runner` will need a companion update for Stage 5's trace.

## Out of scope

- `bench/runner.py` CLI bloat (lines 149-end). The `argparse` setup is in the same module as `run_suite` but that's separate friction worth its own pass.
- Any web-layer refactoring beyond what Stage 4 forces.
