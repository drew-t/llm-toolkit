"""Tests for the suite runner."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

from llm_toolkit.bench.runner import SuiteResult, run_suite
from llm_toolkit.bench.suite import Suite, TestCase
from llm_toolkit.providers.base import Response


def _make_mock_provider(responses: list[str]) -> AsyncMock:
    provider = AsyncMock()
    provider.chat = AsyncMock(
        side_effect=[
            Response(text=t, prefill_tok_s=100, decode_tok_s=50,
                     prompt_tokens=10, gen_tokens=5, wall_time_s=0.1)
            for t in responses
        ]
    )
    return provider


def test_run_suite_basic():
    provider = _make_mock_provider(["world", "bar"])
    def exact(text, expected):
        return 1.0 if text.strip() == expected else 0.0
    suite = Suite(
        name="test",
        cases=[
            TestCase(key="t1", prompt="hello", expected="world"),
            TestCase(key="t2", prompt="foo", expected="bar"),
        ],
        default_score_fn=exact,
    )
    result = asyncio.run(run_suite(provider, "test-model", suite))
    assert isinstance(result, SuiteResult)
    assert result.suite_name == "test"
    assert len(result.case_results) == 2
    assert all(cr.score == 1.0 for cr in result.case_results)


def test_run_suite_mixed_scores():
    provider = _make_mock_provider(["world", "wrong"])
    def exact(text, expected):
        return 1.0 if text.strip() == expected else 0.0
    suite = Suite(
        name="test",
        cases=[
            TestCase(key="t1", prompt="hello", expected="world"),
            TestCase(key="t2", prompt="foo", expected="bar"),
        ],
        default_score_fn=exact,
    )
    result = asyncio.run(run_suite(provider, "test-model", suite))
    assert result.case_results[0].score == 1.0
    assert result.case_results[1].score == 0.0


def test_run_suite_no_scorer():
    provider = _make_mock_provider(["response"])
    suite = Suite(name="test", cases=[TestCase(key="t1", prompt="hello")])
    result = asyncio.run(run_suite(provider, "test-model", suite))
    assert result.case_results[0].score is None


def test_run_suite_case_scorer_overrides():
    provider = _make_mock_provider(["response"])
    def suite_fn(text, expected):
        return 0.0
    def case_fn(text, expected):
        return 1.0
    suite = Suite(
        name="test",
        cases=[TestCase(key="t1", prompt="q", expected="a", score_fn=case_fn)],
        default_score_fn=suite_fn,
    )
    result = asyncio.run(run_suite(provider, "test-model", suite))
    assert result.case_results[0].score == 1.0
