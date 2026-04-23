"""Tests for the context scaling (GraphWalks) built-in suite."""

from __future__ import annotations

import random

from llm_toolkit.bench.context import (
    context_scaling_suite,
    extract_answer_nodes,
    f1_score,
    generate_fixture,
)


def test_f1_score_perfect():
    assert f1_score({"a", "b", "c"}, {"a", "b", "c"}) == 1.0


def test_f1_score_partial():
    score = f1_score({"a", "b"}, {"a", "b", "c"})
    assert 0.79 < score < 0.81


def test_f1_score_empty():
    assert f1_score(set(), set()) == 1.0
    assert f1_score(set(), {"a"}) == 0.0
    assert f1_score({"a"}, set()) == 0.0


def test_extract_answer_nodes():
    text = "Final Answer: [abc123, def456, ghi789]"
    nodes = extract_answer_nodes(text)
    assert nodes == {"abc123", "def456", "ghi789"}


def test_extract_answer_nodes_not_found():
    assert extract_answer_nodes("no answer here") == set()


def test_extract_answer_nodes_quoted():
    text = "Final Answer: ['abc', \"def\"]"
    nodes = extract_answer_nodes(text)
    assert nodes == {"abc", "def"}


def test_generate_fixture():
    rng = random.Random(42)
    fx = generate_fixture(1000, rng)
    assert fx["target_tokens"] == 1000
    assert "prompt" in fx
    assert "answer_nodes" in fx
    assert len(fx["answer_nodes"]) >= 2


def test_context_scaling_suite():
    suite = context_scaling_suite()
    assert suite.name == "context_scaling"
    assert len(suite.cases) > 0
    for tc in suite.cases:
        assert "answer_nodes" in tc.metadata
