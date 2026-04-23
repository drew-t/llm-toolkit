"""Tests for Suite and TestCase dataclasses."""

from __future__ import annotations

from llm_toolkit.bench.suite import Suite, TestCase


def test_testcase_minimal():
    tc = TestCase(key="t1", prompt="hello")
    assert tc.key == "t1"
    assert tc.expected is None
    assert tc.score_fn is None
    assert tc.metadata == {}


def test_testcase_with_scorer():
    def exact_match(text, expected):
        return 1.0 if text.strip() == expected else 0.0
    tc = TestCase(key="t1", prompt="hello", expected="world", score_fn=exact_match)
    assert tc.score_fn("world", "world") == 1.0
    assert tc.score_fn("nope", "world") == 0.0


def test_suite_creation():
    cases = [
        TestCase(key="t1", prompt="hello", expected="world"),
        TestCase(key="t2", prompt="foo", expected="bar"),
    ]
    suite = Suite(name="test", cases=cases)
    assert suite.name == "test"
    assert len(suite.cases) == 2
    assert suite.system_prompt == ""


def test_suite_with_default_scorer():
    def contains(text, expected):
        return 1.0 if expected.lower() in text.lower() else 0.0
    suite = Suite(
        name="test",
        cases=[TestCase(key="t1", prompt="q", expected="answer")],
        default_score_fn=contains,
    )
    assert suite.default_score_fn("The answer is 42", "answer") == 1.0


def test_testcase_scorer_overrides_suite():
    def suite_fn(text, expected):
        return 0.5
    def case_fn(text, expected):
        return 1.0
    suite = Suite(
        name="test",
        cases=[TestCase(key="t1", prompt="q", expected="a", score_fn=case_fn)],
        default_score_fn=suite_fn,
    )
    tc = suite.cases[0]
    scorer = tc.score_fn or suite.default_score_fn
    assert scorer("x", "a") == 1.0
