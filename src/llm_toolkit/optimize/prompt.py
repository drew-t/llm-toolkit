"""Prompt optimizer: mutation/eval loop for improving LLM prompts."""

from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass, field

from llm_toolkit.bench.measure import WarmStable, measure
from llm_toolkit.bench.scorer import aggregate
from llm_toolkit.bench.suite import Suite
from llm_toolkit.providers.base import Provider

MUTATION_TYPES = [
    "reword_instruction",
    "add_example",
    "remove_example",
    "reorder_sections",
    "adjust_emphasis_up",
    "adjust_emphasis_down",
]

MUTATION_SYSTEM = """\
You are a prompt engineer specializing in tool-use prompts for LLMs.
Your job is to improve prompts that instruct an LLM how to use structured
actions or tools.

Rules:
- Return ONLY the modified prompt text. No explanations, no preamble, no markdown wrapping.
- Preserve the overall structure and any placeholder variables exactly as they appear.
- Do not change JSON schemas or field names.
- Do not add fictional tools or capabilities not in the original.
- The prompt should be roughly the same length (within 30% of original)."""

MUTATION_PROMPTS = {
    "reword_instruction": (
        "Reword the instructions to be clearer and more precise."
        " Use more direct, imperative language."
    ),
    "add_example": (
        "Add one additional concrete example that demonstrates a common use case"
        " not already covered."
    ),
    "remove_example": (
        "Remove the least informative example to make the prompt more concise."
        " Keep at least two examples."
    ),
    "reorder_sections": "Reorder sections so the most critical information comes first.",
    "adjust_emphasis_up": (
        "Make 1-2 of the most important instructions more emphatic (CAPS, 'Important:' prefixes)."
    ),
    "adjust_emphasis_down": "Reduce excessive emphasis. Make the tone more neutral and direct.",
}


@dataclass
class MutationRecord:
    iteration: int
    mutation: str
    score: float
    improved: bool
    duration: float = 0.0
    detail: str = ""


@dataclass
class OptimizeResult:
    original_prompt: str
    original_score: float
    best_prompt: str
    best_score: float
    mutation_history: list[MutationRecord] = field(default_factory=list)
    total_duration: float = 0.0


@dataclass
class OptimizeConfig:
    prompt_text: str
    eval_suite: Suite
    provider: Provider
    model: str
    mutator_model: str | None = None
    iterations: int = 10
    results_path: str | None = None
    measurement_repetitions: int = 3


async def _mutate(provider: Provider, model: str, prompt: str, mutation_type: str) -> str:
    instruction = MUTATION_PROMPTS[mutation_type]
    user_msg = (
        f"Here is a prompt for an LLM:\n\n---\n{prompt}\n---\n\n"
        f"{instruction}\n\nReturn ONLY the modified prompt text."
    )

    resp = await provider.chat(
        model,
        [
            {"role": "system", "content": MUTATION_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        max_tokens=8192,
        temperature=0.8,
    )

    result = resp.text.strip()
    result = re.sub(r"<think>.*?</think>\s*", "", result, flags=re.DOTALL).strip()
    result = re.sub(r"^```[\w]*\n", "", result)
    result = re.sub(r"\n```$", "", result)

    if len(result.strip()) < 50:
        msg = f"Mutation produced suspiciously short result ({len(result)} chars)"
        raise ValueError(msg)

    return result.strip()


async def _evaluate(
    provider: Provider, model: str, suite: Suite, *, repetitions: int,
) -> float:
    """Evaluate a candidate against the suite under WarmStable measurement.

    Repetitions denoise scoring; warmup eliminates first-call cold-start bias.
    """
    result = await measure(
        provider, model, suite, strategy=WarmStable(repetitions=repetitions),
    )
    scores = [cr.score for cr in result.case_results if cr.error is None]
    mean = aggregate(scores)
    return mean * 100 if mean is not None else 0.0


async def optimize_prompt(config: OptimizeConfig) -> OptimizeResult:
    mutator_model = config.mutator_model or config.model

    baseline_score = await _evaluate(
        config.provider, config.model, config.eval_suite,
        repetitions=config.measurement_repetitions,
    )

    best_prompt = config.prompt_text
    best_score = baseline_score
    history: list[MutationRecord] = []
    t_start = time.monotonic()

    for i in range(config.iterations):
        mutation_type = random.choice(MUTATION_TYPES)
        t_iter = time.monotonic()

        try:
            candidate = await _mutate(config.provider, mutator_model, best_prompt, mutation_type)
        except Exception as e:
            history.append(
                MutationRecord(
                    iteration=i + 1,
                    mutation=mutation_type,
                    score=best_score,
                    improved=False,
                    detail=f"mutation error: {e}",
                )
            )
            continue

        modified_suite = Suite(
            name=config.eval_suite.name,
            cases=config.eval_suite.cases,
            system_prompt=candidate,
            default_score_fn=config.eval_suite.default_score_fn,
            provider_opts=config.eval_suite.provider_opts,
        )

        try:
            score = await _evaluate(
                config.provider, config.model, modified_suite,
                repetitions=config.measurement_repetitions,
            )
        except Exception as e:
            history.append(
                MutationRecord(
                    iteration=i + 1,
                    mutation=mutation_type,
                    score=best_score,
                    improved=False,
                    detail=f"eval error: {e}",
                )
            )
            continue

        iter_duration = time.monotonic() - t_iter
        improved = score > best_score

        if improved:
            best_prompt = candidate
            best_score = score

        history.append(
            MutationRecord(
                iteration=i + 1,
                mutation=mutation_type,
                score=score,
                improved=improved,
                duration=iter_duration,
            )
        )

    return OptimizeResult(
        original_prompt=config.prompt_text,
        original_score=baseline_score,
        best_prompt=best_prompt,
        best_score=best_score,
        mutation_history=history,
        total_duration=time.monotonic() - t_start,
    )
