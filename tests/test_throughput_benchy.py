"""Tests for the llama-benchy wrapper (parsing + argv construction)."""

from __future__ import annotations

from pathlib import Path

from llm_toolkit.bench.throughput_benchy import (
    BenchyConfig,
    print_report_summary,
    report_to_bench_results,
)


def _sample_report() -> dict:
    return {
        "version": "0.1.0",
        "timestamp": "2026-04-28T00:00:00Z",
        "latency_mode": "api",
        "latency_ms": 1.2,
        "model": "qwen3:8b",
        "prefix_caching_enabled": False,
        "max_concurrency": 1,
        "benchmarks": [
            {
                "concurrency": 1,
                "context_size": 0,
                "prompt_size": 2048,
                "response_size": 32,
                "is_context_prefill_phase": False,
                "pp_throughput": {"mean": 1234.5, "std": 12.3, "values": [1234.5]},
                "pp_req_throughput": {"mean": 1234.5, "std": 12.3, "values": [1234.5]},
                "tg_throughput": {"mean": 78.9, "std": 1.0, "values": [78.9]},
                "tg_req_throughput": {"mean": 78.9, "std": 1.0, "values": [78.9]},
                "ttfr": {"mean": 110.0, "std": 5.0, "values": [110.0]},
                "est_ppt": {"mean": 100.0, "std": 5.0, "values": [100.0]},
                "e2e_ttft": {"mean": 115.0, "std": 5.0, "values": [115.0]},
                "peak_throughput": None,
                "peak_req_throughput": None,
            },
            {
                "concurrency": 4,
                "context_size": 4096,
                "prompt_size": 2048,
                "response_size": 32,
                "is_context_prefill_phase": True,
                "pp_throughput": {"mean": 4321.0, "std": 50.0, "values": [4321.0]},
                "tg_throughput": None,
                "ttfr": {"mean": 220.0, "std": 10.0, "values": [220.0]},
                "e2e_ttft": {"mean": 240.0, "std": 12.0, "values": [240.0]},
                "est_ppt": {"mean": 200.0, "std": 8.0, "values": [200.0]},
            },
        ],
    }


def test_argv_includes_required_flags(tmp_path: Path):
    cfg = BenchyConfig(
        base_url="http://host:8000/v1",
        model="qwen3:8b",
        pp=[2048, 4096],
        tg=[32],
        depth=[0, 4096],
        concurrency=[1, 4],
        runs=2,
        enable_prefix_caching=True,
        no_cache=False,
        extra_args=["--book-url", "https://example.com/book.txt"],
    )
    argv = cfg.to_argv(save_result=tmp_path / "out.json")
    assert argv[:2] == ["uvx", "llama-benchy"]
    assert "--base-url" in argv and "http://host:8000/v1" in argv
    assert "--model" in argv and "qwen3:8b" in argv
    assert "--pp" in argv and "2048" in argv and "4096" in argv
    assert "--depth" in argv and "0" in argv
    assert "--concurrency" in argv and "4" in argv
    assert "--runs" in argv and "2" in argv
    assert "--enable-prefix-caching" in argv
    assert "--no-cache" not in argv
    assert "--book-url" in argv
    assert "--save-result" in argv and "--format" in argv and "json" in argv


def test_argv_command_override(tmp_path: Path):
    cfg = BenchyConfig(
        base_url="http://h:8000/v1",
        command=["llama-benchy"],
    )
    argv = cfg.to_argv(save_result=tmp_path / "out.json")
    assert argv[0] == "llama-benchy"


def test_report_to_bench_results_flattens_metrics():
    rows = report_to_bench_results(_sample_report(), model_override="qwen3:8b")
    assert len(rows) == 2

    first = rows[0]
    assert first.benchmark == "throughput_benchy"
    assert first.model == "qwen3:8b"
    assert first.metrics["pp_throughput"] == 1234.5
    assert first.metrics["tg_throughput"] == 78.9
    assert first.metrics["e2e_ttft"] == 115.0
    assert first.metadata["key"] == "c1_pp2048_tg32_d0"
    assert first.metadata["std"]["tg_throughput"] == 1.0
    assert first.metadata["concurrency"] == 1

    second = rows[1]
    assert second.metadata["key"] == "c4_pp2048_tg32_d4096_prefill"
    assert "tg_throughput" not in second.metrics  # null in source
    assert second.metrics["pp_throughput"] == 4321.0


def test_report_to_bench_results_default_model_from_report():
    rows = report_to_bench_results(_sample_report())
    assert rows[0].model == "qwen3:8b"


def test_report_to_bench_results_handles_empty():
    rows = report_to_bench_results({"benchmarks": []})
    assert rows == []


def test_print_report_summary_runs(capsys):
    print_report_summary(_sample_report())
    out = capsys.readouterr().out
    assert "llama-benchy" in out
    assert "c1_pp2048_tg32_d0" in out
    assert "c4_pp2048_tg32_d4096_prefill" in out
