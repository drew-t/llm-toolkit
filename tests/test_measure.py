"""Tests for bench/measure.py — unified measurement strategies."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

from llm_toolkit.bench.measure import (
    Direct,
    PerfIsolated,
    WarmStable,
    make_nonce,
    measure,
    nonce_prompt,
)
from llm_toolkit.bench.suite import Suite, TestCase
from llm_toolkit.providers.base import Response


def _provider_returning(text: str = "ok", *, prefill: float = 100.0,
                       decode: float = 50.0, wall: float = 1.0) -> AsyncMock:
    provider = AsyncMock()
    provider.chat = AsyncMock(
        return_value=Response(
            text=text,
            prefill_tok_s=prefill,
            decode_tok_s=decode,
            prompt_tokens=10,
            gen_tokens=5,
            wall_time_s=wall,
        )
    )
    return provider


def _suite_one_case(*, expected: str | None = None,
                    score_fn=None, system_prompt: str = "") -> Suite:
    return Suite(
        name="t",
        cases=[TestCase(key="c1", prompt="q", expected=expected, score_fn=score_fn)],
        system_prompt=system_prompt,
    )


def test_make_nonce_length_and_alnum():
    n = make_nonce()
    assert len(n) == 8
    assert n.isalnum()


def test_make_nonce_unique():
    nonces = {make_nonce() for _ in range(100)}
    assert len(nonces) == 100


def test_nonce_prompt_format():
    p = nonce_prompt("hello")
    assert p.startswith("[run:")
    assert p.endswith("] hello")


def test_direct_default_strategy_one_call_per_case():
    provider = _provider_returning("hi")
    suite = _suite_one_case()
    result = asyncio.run(measure(provider, "m", suite))
    assert provider.chat.await_count == 1
    assert result.case_results[0].response == "hi"
    assert result.case_results[0].repetitions == 1


def test_direct_applies_scorer_via_resolve_scorer():
    provider = _provider_returning("yes")
    suite = _suite_one_case(expected="yes", score_fn=lambda t, e: 1.0 if t == e else 0.0)
    result = asyncio.run(measure(provider, "m", suite, strategy=Direct()))
    assert result.case_results[0].score == 1.0


def test_direct_strip_thinking_default_on():
    provider = _provider_returning("<think>plan</think>final")
    suite = _suite_one_case()
    result = asyncio.run(measure(provider, "m", suite, strategy=Direct()))
    assert result.case_results[0].response == "final"


def test_direct_error_path_records_zero_score():
    provider = AsyncMock()
    provider.chat = AsyncMock(side_effect=RuntimeError("boom"))
    suite = _suite_one_case(expected="x", score_fn=lambda t, e: 1.0)
    result = asyncio.run(measure(provider, "m", suite, strategy=Direct()))
    cr = result.case_results[0]
    assert cr.error == "boom"
    assert cr.score == 0.0


def test_warm_stable_calls_provider_warmup_plus_reps():
    provider = _provider_returning("ok")
    suite = _suite_one_case()
    asyncio.run(measure(provider, "m", suite, strategy=WarmStable(repetitions=3)))
    # 1 warmup + 3 measured = 4 calls
    assert provider.chat.await_count == 4


def test_warm_stable_records_repetitions_and_raw_runs():
    provider = _provider_returning("ok", decode=50.0, wall=1.0)
    suite = _suite_one_case()
    result = asyncio.run(measure(provider, "m", suite, strategy=WarmStable(repetitions=3)))
    cr = result.case_results[0]
    assert cr.repetitions == 3
    assert cr.raw_runs is not None
    assert len(cr.raw_runs) == 3


def test_warm_stable_metrics_are_median_across_reps():
    # Three responses with decode rates 100, 200, 300 — median is 200.
    decode_rates = iter([100.0, 200.0, 300.0])
    wall_times = iter([1.0, 2.0, 3.0])

    async def chat(model, msgs, **kw):
        # warmup uses max_tokens=8; treat that as warmup and return defaults
        if kw.get("max_tokens") == 8:
            return Response(text="warm", prefill_tok_s=0.0, decode_tok_s=0.0,
                            prompt_tokens=0, gen_tokens=0, wall_time_s=0.0)
        return Response(
            text="ok", prefill_tok_s=100.0, decode_tok_s=next(decode_rates),
            prompt_tokens=10, gen_tokens=5, wall_time_s=next(wall_times),
        )

    provider = AsyncMock()
    provider.chat = chat
    suite = _suite_one_case()
    result = asyncio.run(measure(provider, "m", suite, strategy=WarmStable(repetitions=3)))
    cr = result.case_results[0]
    assert cr.decode_tok_s == 200.0
    assert cr.wall_time_s == 2.0


def test_perf_isolated_each_rep_is_unique_prompt():
    seen_user_msgs: list[str] = []

    async def chat(model, msgs, **kw):
        # Skip warmup
        if kw.get("max_tokens") == 8:
            return Response(text="warm", prefill_tok_s=0.0, decode_tok_s=0.0,
                            prompt_tokens=0, gen_tokens=0, wall_time_s=0.0)
        seen_user_msgs.append(msgs[-1]["content"])
        return Response(text="ok", prefill_tok_s=100.0, decode_tok_s=50.0,
                        prompt_tokens=10, gen_tokens=5, wall_time_s=1.0)

    provider = AsyncMock()
    provider.chat = chat
    suite = _suite_one_case()
    asyncio.run(measure(provider, "m", suite, strategy=PerfIsolated(repetitions=3)))
    assert len(seen_user_msgs) == 3
    assert len(set(seen_user_msgs)) == 3  # all distinct (nonce applied)
    for m in seen_user_msgs:
        assert m.startswith("[run:")


def test_warm_stable_no_nonce_in_user_message():
    seen: list[str] = []

    async def chat(model, msgs, **kw):
        if kw.get("max_tokens") == 8:
            return Response(text="warm", prefill_tok_s=0.0, decode_tok_s=0.0,
                            prompt_tokens=0, gen_tokens=0, wall_time_s=0.0)
        seen.append(msgs[-1]["content"])
        return Response(text="ok", prefill_tok_s=100.0, decode_tok_s=50.0,
                        prompt_tokens=10, gen_tokens=5, wall_time_s=1.0)

    provider = AsyncMock()
    provider.chat = chat
    suite = _suite_one_case()
    asyncio.run(measure(provider, "m", suite, strategy=WarmStable(repetitions=2)))
    for m in seen:
        assert not m.startswith("[run:")


def test_system_prompt_threaded_through_to_provider():
    provider = _provider_returning("ok")
    suite = _suite_one_case(system_prompt="be terse")
    asyncio.run(measure(provider, "m", suite, strategy=Direct()))
    msgs = provider.chat.await_args.args[1]
    assert msgs[0] == {"role": "system", "content": "be terse"}
