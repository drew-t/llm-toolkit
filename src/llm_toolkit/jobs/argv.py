"""Translate a planned run into the CLI argv that executes it.

The web UI never re-implements benchmark logic — it just shells out to
the same `llm-toolkit` CLI a human would type. This module is the only
place that knows the mapping (benchmark → subcommand → flags).
"""

from __future__ import annotations

from typing import Any

PERF_BENCHMARKS = {"throughput_benchy"}
ACCURACY_BENCHMARKS = {"context_scaling", "classifier", "throughput", "coding"}


def build_argv(
    *,
    benchmark: str,
    model: str,
    base_url: str,
    results_path: str,
    args: dict[str, Any],
) -> list[str]:
    if benchmark in PERF_BENCHMARKS:
        return _perf_argv(model, base_url, results_path, args, benchmark=benchmark)
    if benchmark in ACCURACY_BENCHMARKS:
        return _accuracy_argv(benchmark, model, base_url, results_path, args)
    raise ValueError(f"unknown benchmark: {benchmark!r}")


def _perf_argv(
    model: str,
    base_url: str,
    results_path: str,
    args: dict[str, Any],
    *,
    benchmark: str,
) -> list[str]:
    argv: list[str] = [
        "llm-toolkit", "bench-perf",
        "--url", base_url,
        "--models", model,
        "--results", results_path,
        "--benchmark-name", benchmark,
    ]
    for key in ("pp", "tg", "depth", "concurrency"):
        v = args.get(key)
        if v:
            argv.append(f"--{key}")
            argv.extend(str(x) for x in v)
    if args.get("runs") is not None:
        argv += ["--runs", str(args["runs"])]
    if args.get("tokenizer"):
        argv += ["--tokenizer", args["tokenizer"]]
    if args.get("served_model_name"):
        argv += ["--served-model-name", args["served_model_name"]]
    if args.get("prefix_caching"):
        argv += ["--prefix-caching"]
    if args.get("no_cache"):
        argv += ["--no-cache"]
    if args.get("skip_coherence"):
        argv += ["--skip-coherence"]
    if args.get("no_warmup"):
        argv += ["--no-warmup"]
    return argv


def _accuracy_argv(
    benchmark: str, model: str, base_url: str,
    results_path: str, args: dict[str, Any],
) -> list[str]:
    argv = [
        "llm-toolkit", "bench",
        "--suite", benchmark,
        "--models", model,
        "--url", base_url,
        "--results", results_path,
    ]
    if args.get("provider"):
        argv += ["--provider", args["provider"]]
    return argv
