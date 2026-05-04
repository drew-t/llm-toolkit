"""Scoring: resolve precedence (case > suite > none) and aggregate scores.

The interface every caller crosses to score a benchmark response. Replaces
the inline scorer-resolution logic that was scattered across `run_suite`
and `optimize.prompt._evaluate`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

ScoreFn = Callable[[str, str], float]


def resolve_scorer(
    case_scorer: ScoreFn | None,
    suite_scorer: ScoreFn | None,
) -> ScoreFn | None:
    """Pick a scorer using the precedence rule: case > suite > none."""
    return case_scorer or suite_scorer


def aggregate(scores: Iterable[float | None]) -> float | None:
    """Mean of non-None scores. Returns None when no scores are present.

    Aggregation lives here, not in callers, so the rule for what counts as
    a "score" (non-None) stays in one place.
    """
    valid = [s for s in scores if s is not None]
    if not valid:
        return None
    return sum(valid) / len(valid)


def exact_match_scorer(text: str, expected: str) -> float:
    """Strict equality on the first line, case-insensitive, pipe-trimmed."""
    cleaned = text.strip().lower().split("\n")[0]
    if "|" in cleaned:
        cleaned = cleaned.split("|")[0].strip()
    return 1.0 if cleaned == expected.strip().lower() else 0.0
