"""Throughput benchmarking via the llama-benchy CLI.

Shells out to `llama-benchy` (default invocation: `uvx llama-benchy`) and
parses its JSON report into BenchResult records for the toolkit's ResultStore.

Schema reference: https://github.com/eugr/llama-benchy/blob/main/schemas/benchmark_report_schema.json
"""

from __future__ import annotations

import json
import shlex
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from llm_toolkit.results import BenchResult

DEFAULT_CMD = ["uvx", "llama-benchy"]

HEADLINE_METRIC_KEYS = (
    "pp_throughput",
    "pp_req_throughput",
    "tg_throughput",
    "tg_req_throughput",
    "peak_throughput",
    "peak_req_throughput",
    "ttfr",
    "est_ppt",
    "e2e_ttft",
)


@dataclass
class BenchyConfig:
    base_url: str
    model: str | None = None
    api_key: str | None = None
    served_model_name: str | None = None
    tokenizer: str | None = None
    pp: list[int] | None = None
    tg: list[int] | None = None
    depth: list[int] | None = None
    runs: int | None = None
    concurrency: list[int] | None = None
    enable_prefix_caching: bool = False
    no_cache: bool = False
    skip_coherence: bool = False
    no_warmup: bool = False
    extra_args: list[str] | None = None
    command: list[str] | None = None  # override how llama-benchy is invoked

    def to_argv(self, *, save_result: Path) -> list[str]:
        argv: list[str] = list(self.command or DEFAULT_CMD)
        argv += ["--base-url", self.base_url]
        if self.model:
            argv += ["--model", self.model]
        if self.api_key:
            argv += ["--api-key", self.api_key]
        if self.served_model_name:
            argv += ["--served-model-name", self.served_model_name]
        if self.tokenizer:
            argv += ["--tokenizer", self.tokenizer]
        if self.pp:
            argv += ["--pp", *map(str, self.pp)]
        if self.tg:
            argv += ["--tg", *map(str, self.tg)]
        if self.depth:
            argv += ["--depth", *map(str, self.depth)]
        if self.concurrency:
            argv += ["--concurrency", *map(str, self.concurrency)]
        if self.runs is not None:
            argv += ["--runs", str(self.runs)]
        if self.enable_prefix_caching:
            argv += ["--enable-prefix-caching"]
        if self.no_cache:
            argv += ["--no-cache"]
        if self.skip_coherence:
            argv += ["--skip-coherence"]
        if self.no_warmup:
            argv += ["--no-warmup"]
        if self.extra_args:
            argv += list(self.extra_args)
        argv += ["--save-result", str(save_result), "--format", "json"]
        return argv


def run_benchy(cfg: BenchyConfig, *, timeout: float | None = None) -> dict[str, Any]:
    """Run llama-benchy and return the parsed JSON report.

    Stdout/stderr stream through to the parent — the user sees progress
    (and any uvx install noise) in real time.
    """
    with tempfile.TemporaryDirectory() as td:
        out_path = Path(td) / "benchy.json"
        argv = cfg.to_argv(save_result=out_path)
        print(f"+ {shlex.join(argv)}")
        proc = subprocess.run(argv, timeout=timeout, check=False)
        if proc.returncode != 0:
            raise RuntimeError(f"llama-benchy exited with status {proc.returncode}")
        if not out_path.exists():
            raise RuntimeError(f"llama-benchy produced no result file at {out_path}")
        with out_path.open() as f:
            return json.load(f)


def _metric_mean(metric: Any) -> float | None:
    if isinstance(metric, dict):
        v = metric.get("mean")
        return float(v) if v is not None else None
    return None


def _metric_std(metric: Any) -> float | None:
    if isinstance(metric, dict):
        v = metric.get("std")
        return float(v) if v is not None else None
    return None


def _row_key(row: dict[str, Any]) -> str:
    parts = [
        f"c{row.get('concurrency', '?')}",
        f"pp{row.get('prompt_size', '?')}",
        f"tg{row.get('response_size', '?')}",
        f"d{row.get('context_size', '?')}",
    ]
    if row.get("is_context_prefill_phase"):
        parts.append("prefill")
    return "_".join(str(p) for p in parts)


def report_to_bench_results(
    report: dict[str, Any],
    *,
    benchmark: str = "throughput_benchy",
    model_override: str | None = None,
) -> list[BenchResult]:
    """Flatten a llama-benchy report into BenchResult rows (one per benchmark entry)."""
    model = model_override or report.get("model") or "unknown"
    ts = time.time()
    out: list[BenchResult] = []
    for row in report.get("benchmarks", []):
        metrics: dict[str, Any] = {}
        stds: dict[str, float] = {}
        for key in HEADLINE_METRIC_KEYS:
            mean = _metric_mean(row.get(key))
            if mean is not None:
                metrics[key] = mean
            std = _metric_std(row.get(key))
            if std is not None:
                stds[key] = std
        out.append(
            BenchResult(
                benchmark=benchmark,
                model=model,
                timestamp=ts,
                metrics=metrics,
                metadata={
                    "key": _row_key(row),
                    "concurrency": row.get("concurrency"),
                    "prompt_size": row.get("prompt_size"),
                    "response_size": row.get("response_size"),
                    "context_size": row.get("context_size"),
                    "is_context_prefill_phase": row.get("is_context_prefill_phase"),
                    "std": stds,
                    "version": report.get("version"),
                    "latency_mode": report.get("latency_mode"),
                    "latency_ms": report.get("latency_ms"),
                    "prefix_caching_enabled": report.get("prefix_caching_enabled"),
                },
            )
        )
    return out


def print_report_summary(report: dict[str, Any]) -> None:
    rows = report.get("benchmarks", [])
    print(f"\nllama-benchy v{report.get('version', '?')} | model: {report.get('model', '?')} "
          f"| prefix_cache={report.get('prefix_caching_enabled')} | rows={len(rows)}")
    header = f"{'config':<28} {'pp tok/s':>10} {'tg tok/s':>10} {'ttfr ms':>10} {'e2e ttft ms':>12}"
    print(header)
    print("-" * len(header))
    for row in rows:
        pp = _metric_mean(row.get("pp_throughput"))
        tg = _metric_mean(row.get("tg_throughput"))
        ttfr = _metric_mean(row.get("ttfr"))
        e2e = _metric_mean(row.get("e2e_ttft"))
        print(
            f"{_row_key(row):<28} "
            f"{(pp if pp is not None else 0):>10.1f} "
            f"{(tg if tg is not None else 0):>10.1f} "
            f"{(ttfr if ttfr is not None else 0):>10.1f} "
            f"{(e2e if e2e is not None else 0):>12.1f}"
        )
