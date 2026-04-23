"""Suite and TestCase dataclasses for benchmark definitions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TestCase:
    """A single benchmark test case."""

    key: str
    prompt: str
    expected: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    score_fn: Callable[[str, str], float] | None = None
    messages: list[dict[str, str]] | None = None  # Override prompt with full message list


@dataclass
class Suite:
    """A benchmark suite: a collection of test cases with shared config."""

    name: str
    cases: list[TestCase]
    system_prompt: str = ""
    default_score_fn: Callable[[str, str], float] | None = None
    provider_opts: dict[str, Any] = field(default_factory=dict)
