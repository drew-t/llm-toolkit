"""Raw throughput benchmark suite."""

from __future__ import annotations

from llm_toolkit.bench.suite import Suite, TestCase

DEFAULT_CONTEXT_SIZES = [256, 512, 1024, 2048, 4096, 8192]


def _make_padding(target_tokens: int) -> str:
    words_needed = int(target_tokens / 1.3)
    base = "The quick brown fox jumps over the lazy dog. "
    repeated = (base * (words_needed // 9 + 1))[:words_needed * 5]
    return repeated


def throughput_suite(context_sizes: list[int] | None = None) -> Suite:
    sizes = context_sizes or DEFAULT_CONTEXT_SIZES
    cases = []
    for size in sizes:
        padding = _make_padding(size)
        prompt = f"{padding}\n\nSummarize the above text in one sentence."
        cases.append(TestCase(
            key=f"throughput_{size}",
            prompt=prompt,
            metadata={"context_tokens": size},
        ))
    return Suite(
        name="throughput", cases=cases,
        provider_opts={"max_tokens": 128, "temperature": 0.0},
    )
