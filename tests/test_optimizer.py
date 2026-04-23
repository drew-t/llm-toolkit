"""Tests for the prompt optimization loop."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

from llm_toolkit.bench.suite import Suite, TestCase
from llm_toolkit.optimize.prompt import (
    MUTATION_TYPES,
    OptimizeConfig,
    OptimizeResult,
    optimize_prompt,
)
from llm_toolkit.providers.base import Response


def _make_provider(response_text: str = "result") -> AsyncMock:
    provider = AsyncMock()
    provider.chat = AsyncMock(
        return_value=Response(
            text=response_text,
            prefill_tok_s=100,
            decode_tok_s=50,
            prompt_tokens=10,
            gen_tokens=5,
            wall_time_s=0.1,
        )
    )
    return provider


def test_mutation_types_exist():
    assert len(MUTATION_TYPES) >= 4
    assert "reword_instruction" in MUTATION_TYPES
    assert "add_example" in MUTATION_TYPES


def test_optimize_config():
    config = OptimizeConfig(
        prompt_text="test prompt",
        eval_suite=Suite(name="test", cases=[]),
        provider=_make_provider(),
        model="test-model",
        iterations=1,
    )
    assert config.prompt_text == "test prompt"
    assert config.mutator_model is None


def test_optimize_result():
    r = OptimizeResult(
        original_prompt="old",
        original_score=50.0,
        best_prompt="new",
        best_score=75.0,
        mutation_history=[],
        total_duration=10.0,
    )
    assert r.best_score > r.original_score


def test_optimize_prompt_runs():
    """Integration test: optimizer runs without errors on trivial input."""
    long_response = "mutated prompt text that is long enough to pass validation check easily"
    provider = _make_provider(long_response)

    def always_score(text, expected):
        return 1.0

    suite = Suite(
        name="test",
        cases=[TestCase(key="t1", prompt="q", expected="a")],
        default_score_fn=always_score,
    )

    config = OptimizeConfig(
        prompt_text="Original prompt text for testing",
        eval_suite=suite,
        provider=provider,
        model="test-model",
        iterations=1,
    )

    result = asyncio.run(optimize_prompt(config))
    assert isinstance(result, OptimizeResult)
    assert result.original_prompt == "Original prompt text for testing"
    assert len(result.mutation_history) == 1
