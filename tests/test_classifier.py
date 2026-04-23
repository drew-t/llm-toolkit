"""Tests for the classifier evaluation suite."""

from __future__ import annotations

from llm_toolkit.bench.classifier import (
    build_classifier_suite,
    exact_match_scorer,
    score_results_by_category,
)
from llm_toolkit.bench.runner import CaseResult


def test_exact_match_scorer():
    assert exact_match_scorer("hello", "hello") == 1.0
    assert exact_match_scorer("HELLO", "hello") == 1.0
    assert exact_match_scorer("  hello  ", "hello") == 1.0
    assert exact_match_scorer("hello|reason", "hello") == 1.0
    assert exact_match_scorer("wrong", "hello") == 0.0


def test_build_classifier_suite():
    examples = [
        {"input": "turn on lights", "label": "michelangelo", "category": "easy"},
        {"input": "what's the weather", "label": "april", "category": "easy"},
    ]
    suite = build_classifier_suite(
        name="test_routing", examples=examples, system_prompt="Classify the input.",
    )
    assert suite.name == "test_routing"
    assert len(suite.cases) == 2
    assert suite.cases[0].expected == "michelangelo"
    assert suite.cases[0].metadata["category"] == "easy"


def test_score_results_by_category():
    results = [
        CaseResult(key="t1", response="a", score=1.0, wall_time_s=0.1,
                   prompt_tokens=10, gen_tokens=5, prefill_tok_s=100, decode_tok_s=50),
        CaseResult(key="t2", response="b", score=0.0, wall_time_s=0.1,
                   prompt_tokens=10, gen_tokens=5, prefill_tok_s=100, decode_tok_s=50),
        CaseResult(key="t3", response="c", score=1.0, wall_time_s=0.1,
                   prompt_tokens=10, gen_tokens=5, prefill_tok_s=100, decode_tok_s=50),
    ]
    categories = {"t1": "easy", "t2": "easy", "t3": "hard"}
    breakdown = score_results_by_category(results, categories)
    assert breakdown["easy"]["accuracy"] == 0.5
    assert breakdown["hard"]["accuracy"] == 1.0
