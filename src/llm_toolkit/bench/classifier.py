"""Classification accuracy evaluation suite."""

from __future__ import annotations

from collections.abc import Callable

from llm_toolkit.bench.runner import CaseResult
from llm_toolkit.bench.suite import Suite, TestCase


def exact_match_scorer(text: str, expected: str) -> float:
    cleaned = text.strip().lower().split("\n")[0]
    if "|" in cleaned:
        cleaned = cleaned.split("|")[0].strip()
    return 1.0 if cleaned == expected.strip().lower() else 0.0


def build_classifier_suite(
    name: str,
    examples: list[dict],
    system_prompt: str,
    *,
    input_field: str = "input",
    label_field: str = "label",
    category_field: str = "category",
    scorer: Callable[[str, str], float] | None = None,
) -> Suite:
    cases = []
    for i, ex in enumerate(examples):
        cases.append(TestCase(
            key=f"{name}_{i}",
            prompt=ex[input_field],
            expected=ex[label_field],
            score_fn=scorer or exact_match_scorer,
            metadata={"category": ex.get(category_field, "default")},
        ))
    return Suite(
        name=name, cases=cases, system_prompt=system_prompt,
        default_score_fn=scorer or exact_match_scorer,
        provider_opts={"max_tokens": 10, "temperature": 0.0},
    )


def score_results_by_category(
    results: list[CaseResult],
    categories: dict[str, str],
) -> dict[str, dict]:
    by_cat: dict[str, dict] = {}
    for cr in results:
        cat = categories.get(cr.key, "default")
        if cat not in by_cat:
            by_cat[cat] = {"correct": 0, "total": 0}
        by_cat[cat]["total"] += 1
        if cr.score is not None and cr.score >= 1.0:
            by_cat[cat]["correct"] += 1
    for cat_data in by_cat.values():
        t = cat_data["total"]
        cat_data["accuracy"] = cat_data["correct"] / t if t else 0.0
    return by_cat


def classifier_suite() -> Suite:
    """Default empty classifier suite (to be populated by consumers)."""
    return Suite(name="classifier", cases=[])
