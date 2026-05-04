"""Tests for bench/scorer.py — scoring precedence and aggregation."""

from __future__ import annotations

from llm_toolkit.bench.scorer import (
    aggregate,
    exact_match_scorer,
    resolve_scorer,
)


def test_resolve_case_wins_over_suite():
    case_fn = lambda t, e: 1.0  # noqa: E731
    suite_fn = lambda t, e: 0.5  # noqa: E731
    chosen = resolve_scorer(case_fn, suite_fn)
    assert chosen is case_fn


def test_resolve_falls_back_to_suite():
    suite_fn = lambda t, e: 0.5  # noqa: E731
    chosen = resolve_scorer(None, suite_fn)
    assert chosen is suite_fn


def test_resolve_returns_none_when_neither_set():
    assert resolve_scorer(None, None) is None


def test_aggregate_mean_of_non_none():
    assert aggregate([1.0, 0.0, 0.5]) == 0.5


def test_aggregate_ignores_none():
    assert aggregate([1.0, None, 0.0]) == 0.5


def test_aggregate_returns_none_when_no_scored():
    assert aggregate([]) is None
    assert aggregate([None, None]) is None


def test_exact_match_scorer_basic():
    assert exact_match_scorer("hello", "hello") == 1.0
    assert exact_match_scorer("hello", "world") == 0.0


def test_exact_match_scorer_case_insensitive():
    assert exact_match_scorer("Hello", "hello") == 1.0


def test_exact_match_scorer_first_line_only():
    assert exact_match_scorer("hello\nextra junk", "hello") == 1.0


def test_exact_match_scorer_pipe_split():
    assert exact_match_scorer("hello | trailing", "hello") == 1.0
