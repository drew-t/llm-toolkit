"""Unified measurement: one entry point, three strategies.

Replaces the split between `harness.run_warm_isolated` (warmup + nonce + median)
and `bench.runner.run_suite` (case iteration + scoring). The strategy parameter
selects warmup/nonce/repetition behavior; everything else stays uniform.

Strategies:
- `Direct`        — one pass per case, no warmup, no nonce. (Old `run_suite`.)
- `WarmStable`    — warmup + N reps per case, median across reps, no nonce.
                    Use when scoring matters and prompt format must stay stable.
- `PerfIsolated`  — warmup + N reps per case, nonce per rep to bust KV cache.
                    Use for raw perf measurement.
"""

from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass
from statistics import median

from llm_toolkit.bench.scorer import resolve_scorer
from llm_toolkit.bench.suite import Suite, TestCase
from llm_toolkit.providers.base import Provider

_METRIC_KEYS = ("prefill_tok_s", "decode_tok_s", "wall_time_s",
                "prompt_tokens", "gen_tokens")


def make_nonce() -> str:
    return uuid.uuid4().hex[:8]


def nonce_prompt(prompt: str) -> str:
    return f"[run:{make_nonce()}] {prompt}"


def _strip_thinking(text: str) -> str:
    return re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL).strip()


@dataclass
class Direct:
    """Single pass per case. The previous run_suite default."""

    strip_think: bool = True


@dataclass
class WarmStable:
    """Warmup + N reps per case, median metrics, no nonce."""

    repetitions: int = 3
    warmup_prompt: str = "Say hi."
    strip_think: bool = True


@dataclass
class PerfIsolated:
    """Warmup + N reps per case, nonce per rep to bust the KV cache."""

    repetitions: int = 3
    warmup_prompt: str = "Say hi."
    strip_think: bool = True


Strategy = Direct | WarmStable | PerfIsolated


@dataclass
class CaseResult:
    """Per-case outcome. `repetitions` and `raw_runs` are populated when the
    strategy ran more than one measured pass."""

    key: str
    response: str
    score: float | None
    wall_time_s: float
    prompt_tokens: int
    gen_tokens: int
    prefill_tok_s: float
    decode_tok_s: float
    error: str | None = None
    repetitions: int = 1
    raw_runs: list[dict] | None = None


@dataclass
class SuiteResult:
    suite_name: str
    model: str
    case_results: list[CaseResult]
    total_time_s: float = 0.0


async def measure(
    provider: Provider,
    model: str,
    suite: Suite,
    *,
    strategy: Strategy | None = None,
) -> SuiteResult:
    """Run a suite under the given measurement strategy."""
    strategy = strategy or Direct()
    case_results: list[CaseResult] = []
    t_start = time.perf_counter()

    if isinstance(strategy, (WarmStable, PerfIsolated)):
        await _warmup(provider, model, suite, strategy)

    for tc in suite.cases:
        case_results.append(await _measure_case(provider, model, suite, tc, strategy))

    total = time.perf_counter() - t_start
    return SuiteResult(
        suite_name=suite.name,
        model=model,
        case_results=case_results,
        total_time_s=round(total, 3),
    )


async def _warmup(
    provider: Provider, model: str, suite: Suite, strategy: WarmStable | PerfIsolated,
) -> None:
    msgs: list[dict[str, str]] = []
    if suite.system_prompt:
        msgs.append({"role": "system", "content": suite.system_prompt})
    msgs.append({"role": "user", "content": strategy.warmup_prompt})
    try:
        await provider.chat(model, msgs, **{**suite.provider_opts, "max_tokens": 8})
    except Exception as e:
        print(f"  [warmup failed: {e}]")


async def _measure_case(
    provider: Provider, model: str, suite: Suite, tc: TestCase, strategy: Strategy,
) -> CaseResult:
    nonce = isinstance(strategy, PerfIsolated)
    repetitions = 1 if isinstance(strategy, Direct) else strategy.repetitions

    raw_runs: list[dict] = []
    last_text = ""
    err: str | None = None

    for _ in range(repetitions):
        messages = _build_messages(suite, tc, nonce=nonce)
        try:
            resp = await provider.chat(model, messages, **suite.provider_opts)
            last_text = (
                _strip_thinking(resp.text) if strategy.strip_think else resp.text
            )
            raw_runs.append({
                "prefill_tok_s": resp.prefill_tok_s,
                "decode_tok_s": resp.decode_tok_s,
                "wall_time_s": resp.wall_time_s,
                "prompt_tokens": resp.prompt_tokens,
                "gen_tokens": resp.gen_tokens,
            })
        except Exception as e:
            err = str(e)
            break

    if err is not None:
        return CaseResult(
            key=tc.key, response="", score=0.0,
            wall_time_s=0.0, prompt_tokens=0, gen_tokens=0,
            prefill_tok_s=0.0, decode_tok_s=0.0, error=err,
            repetitions=repetitions,
        )

    metrics = _aggregate_runs(raw_runs)
    scorer = resolve_scorer(tc.score_fn, suite.default_score_fn)
    score = scorer(last_text, tc.expected) if scorer and tc.expected is not None else None

    return CaseResult(
        key=tc.key,
        response=last_text,
        score=score,
        wall_time_s=metrics["wall_time_s"],
        prompt_tokens=int(metrics["prompt_tokens"]),
        gen_tokens=int(metrics["gen_tokens"]),
        prefill_tok_s=metrics["prefill_tok_s"],
        decode_tok_s=metrics["decode_tok_s"],
        repetitions=repetitions,
        raw_runs=raw_runs if repetitions > 1 else None,
    )


def _build_messages(suite: Suite, tc: TestCase, *, nonce: bool) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if suite.system_prompt:
        messages.append({"role": "system", "content": suite.system_prompt})
    if tc.messages:
        messages.extend(tc.messages)
    else:
        prompt = nonce_prompt(tc.prompt) if nonce else tc.prompt
        messages.append({"role": "user", "content": prompt})
    return messages


def _aggregate_runs(runs: list[dict]) -> dict[str, float]:
    if len(runs) == 1:
        return {k: float(runs[0].get(k, 0.0) or 0.0) for k in _METRIC_KEYS}
    out: dict[str, float] = {}
    for k in _METRIC_KEYS:
        vals = [float(r[k]) for r in runs if r.get(k) is not None]
        out[k] = round(median(vals), 3) if vals else 0.0
    return out
