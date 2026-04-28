"""Suite runner: execute benchmark suites against providers."""

from __future__ import annotations

import argparse
import asyncio
import importlib
import re
import time
from dataclasses import dataclass
from pathlib import Path

from llm_toolkit.bench.suite import Suite
from llm_toolkit.providers.base import Provider
from llm_toolkit.results import BenchResult, ResultStore


@dataclass
class CaseResult:
    """Result of running a single test case."""

    key: str
    response: str
    score: float | None
    wall_time_s: float
    prompt_tokens: int
    gen_tokens: int
    prefill_tok_s: float
    decode_tok_s: float
    error: str | None = None


@dataclass
class SuiteResult:
    """Result of running a complete suite."""

    suite_name: str
    model: str
    case_results: list[CaseResult]
    total_time_s: float = 0.0


def strip_thinking(text: str) -> str:
    """Strip <think>...</think> blocks from model output."""
    return re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL).strip()


async def run_suite(
    provider: Provider,
    model: str,
    suite: Suite,
    *,
    strip_think: bool = True,
) -> SuiteResult:
    """Run all test cases in a suite against a model."""
    case_results: list[CaseResult] = []
    t_start = time.perf_counter()

    for tc in suite.cases:
        messages: list[dict[str, str]] = []
        if suite.system_prompt:
            messages.append({"role": "system", "content": suite.system_prompt})
        if tc.messages:
            messages.extend(tc.messages)
        else:
            messages.append({"role": "user", "content": tc.prompt})

        try:
            resp = await provider.chat(model, messages, **suite.provider_opts)
            text = strip_thinking(resp.text) if strip_think else resp.text

            scorer = tc.score_fn or suite.default_score_fn
            score = scorer(text, tc.expected) if scorer and tc.expected is not None else None

            case_results.append(CaseResult(
                key=tc.key, response=text, score=score,
                wall_time_s=resp.wall_time_s, prompt_tokens=resp.prompt_tokens,
                gen_tokens=resp.gen_tokens, prefill_tok_s=resp.prefill_tok_s,
                decode_tok_s=resp.decode_tok_s,
            ))
        except Exception as e:
            case_results.append(CaseResult(
                key=tc.key, response="", score=0.0,
                wall_time_s=0.0, prompt_tokens=0, gen_tokens=0,
                prefill_tok_s=0.0, decode_tok_s=0.0, error=str(e),
            ))

    total = time.perf_counter() - t_start
    return SuiteResult(suite_name=suite.name, model=model,
                       case_results=case_results, total_time_s=round(total, 3))


def print_suite_result(result: SuiteResult) -> None:
    """Print a formatted summary of a suite result."""
    scored = [cr for cr in result.case_results if cr.score is not None]
    errored = [cr for cr in result.case_results if cr.error]

    print(f"\n{'='*60}")
    print(f"Suite: {result.suite_name} | Model: {result.model}")
    print(f"{'='*60}")

    for cr in result.case_results:
        status = "ERR" if cr.error else (f"{cr.score:.2f}" if cr.score is not None else "---")
        print(f"  {cr.key:<30} {status:>6}  {cr.wall_time_s:>6.1f}s  "
              f"{cr.gen_tokens:>4} tok  {cr.decode_tok_s:>5.0f} tok/s")

    if scored:
        avg = sum(cr.score for cr in scored) / len(scored)
        print(f"\n  Average score: {avg:.3f} ({len(scored)} scored, {len(errored)} errors)")
    print(f"  Total time: {result.total_time_s:.1f}s")


def load_suite_from_path(suite_path: str) -> Suite:
    """Load a suite from a Python dotted path like 'mypackage.benchmarks:routing_suite'."""
    if ":" in suite_path:
        module_path, func_name = suite_path.rsplit(":", 1)
    else:
        module_path = suite_path
        func_name = "suite"
    mod = importlib.import_module(module_path)
    factory = getattr(mod, func_name)
    return factory()


def suite_results_to_bench_results(result: SuiteResult) -> list[BenchResult]:
    """Convert a SuiteResult to a list of BenchResult for storage."""
    results = []
    for cr in result.case_results:
        results.append(BenchResult(
            benchmark=result.suite_name, model=result.model,
            timestamp=time.time(),
            metrics={
                "score": cr.score, "wall_time_s": cr.wall_time_s,
                "prompt_tokens": cr.prompt_tokens, "gen_tokens": cr.gen_tokens,
                "prefill_tok_s": cr.prefill_tok_s, "decode_tok_s": cr.decode_tok_s,
            },
            metadata={"key": cr.key, "error": cr.error},
        ))
    return results


BUILTIN_SUITES: dict[str, str] = {
    "context_scaling": "llm_toolkit.bench.context:context_scaling_suite",
    "classifier": "llm_toolkit.bench.classifier:classifier_suite",
    "throughput": "llm_toolkit.bench.throughput:throughput_suite",
}


async def async_main() -> None:
    """CLI entry point for running benchmarks."""
    parser = argparse.ArgumentParser(description="llm-toolkit benchmark runner")
    sub = parser.add_subparsers(dest="command")

    bench_p = sub.add_parser("bench", help="Run benchmark suites")
    bench_p.add_argument("--suite", required=True, help="Suite name or Python path (mod:func)")
    bench_p.add_argument("--models", nargs="+", required=True, help="Model name(s)")
    bench_p.add_argument("--url", default="http://localhost:11434", help="Provider URL")
    bench_p.add_argument("--provider", choices=["ollama", "openai"], default="ollama")
    bench_p.add_argument("--results", type=str, default="results.jsonl", help="Results file")

    perf_p = sub.add_parser(
        "bench-perf",
        help="Throughput perf benchmark via llama-benchy (OpenAI-compatible endpoint)",
    )
    perf_p.add_argument("--url", required=True, help="OpenAI-compatible base URL")
    perf_p.add_argument("--models", nargs="+", required=True)
    perf_p.add_argument("--api-key", default=None)
    perf_p.add_argument("--pp", nargs="+", type=int, default=None, help="Prompt-processing tokens")
    perf_p.add_argument("--tg", nargs="+", type=int, default=None, help="Generation token counts")
    perf_p.add_argument("--depth", nargs="+", type=int, default=None, help="Context depths")
    perf_p.add_argument("--concurrency", nargs="+", type=int, default=None)
    perf_p.add_argument("--runs", type=int, default=None)
    perf_p.add_argument("--prefix-caching", action="store_true")
    perf_p.add_argument("--no-cache", action="store_true")
    perf_p.add_argument("--skip-coherence", action="store_true")
    perf_p.add_argument("--no-warmup", action="store_true")
    perf_p.add_argument(
        "--benchy-cmd",
        default=None,
        help="Override how llama-benchy is invoked (e.g. 'llama-benchy' if installed). "
             "Default: 'uvx llama-benchy'",
    )
    perf_p.add_argument("--results", type=str, default="results.jsonl")
    perf_p.add_argument("--benchmark-name", default="throughput_benchy",
                        help="Label written to BenchResult.benchmark")
    perf_p.add_argument(
        "--benchy-arg",
        action="append",
        default=[],
        help="Pass-through arg to llama-benchy (repeatable). Example: --benchy-arg --book-url=...",
    )

    args = parser.parse_args()

    if args.command == "bench":
        await _run_bench_command(args)
        return
    if args.command == "bench-perf":
        _run_bench_perf_command(args)
        return
    parser.print_help()


async def _run_bench_command(args: argparse.Namespace) -> None:
    if args.provider == "ollama":
        from llm_toolkit.providers.ollama import OllamaProvider
        provider = OllamaProvider(base_url=args.url)
    else:
        from llm_toolkit.providers.openai import OpenAIProvider
        provider = OpenAIProvider(base_url=args.url)

    if args.suite in BUILTIN_SUITES:
        suite = load_suite_from_path(BUILTIN_SUITES[args.suite])
    else:
        suite = load_suite_from_path(args.suite)

    store = ResultStore(Path(args.results))

    for model in args.models:
        result = await run_suite(provider, model, suite)
        print_suite_result(result)
        for br in suite_results_to_bench_results(result):
            store.append(br)

    print(f"\nResults saved to {args.results}")


def _run_bench_perf_command(args: argparse.Namespace) -> None:
    from llm_toolkit.bench.throughput_benchy import (
        BenchyConfig,
        print_report_summary,
        report_to_bench_results,
        run_benchy,
    )

    command = args.benchy_cmd.split() if args.benchy_cmd else None
    store = ResultStore(Path(args.results))

    for model in args.models:
        cfg = BenchyConfig(
            base_url=args.url,
            model=model,
            api_key=args.api_key,
            pp=args.pp,
            tg=args.tg,
            depth=args.depth,
            concurrency=args.concurrency,
            runs=args.runs,
            enable_prefix_caching=args.prefix_caching,
            no_cache=args.no_cache,
            skip_coherence=args.skip_coherence,
            no_warmup=args.no_warmup,
            extra_args=args.benchy_arg or None,
            command=command,
        )
        report = run_benchy(cfg)
        print_report_summary(report)
        for br in report_to_bench_results(
            report, benchmark=args.benchmark_name, model_override=model
        ):
            store.append(br)

    print(f"\nResults saved to {args.results}")


def main() -> None:
    """Sync wrapper for CLI entry point."""
    asyncio.run(async_main())
