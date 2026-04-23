"""Measurement harness for warm/isolated LLM benchmark runs.

Provides nonce-based cache-busting, warm-up passes, and median metric
aggregation across iterations.
"""

from __future__ import annotations

import uuid
from statistics import median
from typing import Any

from llm_toolkit.providers.base import Provider

METRIC_KEYS = ["prefill_tok_s", "decode_tok_s", "wall_time_s", "prompt_tokens", "gen_tokens"]


def make_nonce() -> str:
    """Generate a unique 8-char hex nonce."""
    return uuid.uuid4().hex[:8]


def nonce_prompt(prompt: str) -> str:
    """Prefix a unique nonce so every measured run is a true cache miss."""
    return f"[run:{make_nonce()}] {prompt}"


def median_metrics(results: list[dict]) -> dict[str, float]:
    """Compute median of each metric across runs."""
    out: dict[str, float] = {}
    for k in METRIC_KEYS:
        vals = [float(r[k]) for r in results if r.get(k) is not None]
        out[k] = round(median(vals), 3) if vals else 0.0
    return out


async def run_warm_isolated(
    provider: Provider,
    model: str,
    prompt: str,
    *,
    iterations: int = 1,
    warmup_prompt: str = "Say hi.",
    nonce: bool = True,
    system_prompt: str = "",
    **provider_kwargs: Any,
) -> dict[str, Any]:
    """Run with warmup pass + optional nonce isolation. Returns median metrics.

    Set nonce=False for accuracy benchmarks where the prompt format matters.
    """
    messages_base = []
    if system_prompt:
        messages_base.append({"role": "system", "content": system_prompt})

    # Warmup — load model weights into VRAM
    warmup_kw = dict(provider_kwargs)
    warmup_kw["max_tokens"] = 8
    warmup_msgs = [*messages_base, {"role": "user", "content": warmup_prompt}]
    try:
        await provider.chat(model, warmup_msgs, **warmup_kw)
    except Exception as e:
        print(f"  [warmup failed: {e}]")

    # Measured runs
    results: list[dict[str, Any]] = []
    for _ in range(iterations):
        p = nonce_prompt(prompt) if nonce else prompt
        msgs = [*messages_base, {"role": "user", "content": p}]
        resp = await provider.chat(model, msgs, **provider_kwargs)
        results.append({
            "prefill_tok_s": resp.prefill_tok_s,
            "decode_tok_s": resp.decode_tok_s,
            "wall_time_s": resp.wall_time_s,
            "prompt_tokens": resp.prompt_tokens,
            "gen_tokens": resp.gen_tokens,
            "text": resp.text,
        })

    if len(results) == 1:
        return results[0]

    medians = median_metrics(results)
    medians["text"] = results[-1].get("text", "")
    medians["raw_runs"] = results
    medians["iterations"] = iterations
    return medians
