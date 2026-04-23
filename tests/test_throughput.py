"""Tests for the throughput benchmark suite."""

from __future__ import annotations

from llm_toolkit.bench.throughput import throughput_suite


def test_throughput_suite_default():
    suite = throughput_suite()
    assert suite.name == "throughput"
    assert len(suite.cases) > 0
    for tc in suite.cases:
        assert "context_tokens" in tc.metadata


def test_throughput_suite_custom_sizes():
    suite = throughput_suite(context_sizes=[256, 1024])
    assert len(suite.cases) == 2
    tokens = [tc.metadata["context_tokens"] for tc in suite.cases]
    assert 256 in tokens
    assert 1024 in tokens
