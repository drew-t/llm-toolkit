from llm_toolkit.jobs.argv import build_argv


def test_perf_argv_minimal():
    argv = build_argv(
        benchmark="throughput_benchy",
        model="qwen3:8b",
        base_url="http://127.0.0.1:11434/v1",
        results_path="/tmp/run_42.jsonl",
        args={},
    )
    assert argv[:3] == ["llm-toolkit", "bench-perf", "--url"]
    assert "http://127.0.0.1:11434/v1" in argv
    assert "--models" in argv
    assert "qwen3:8b" in argv
    assert "--results" in argv
    assert "/tmp/run_42.jsonl" in argv
    assert "--benchmark-name" in argv
    assert "throughput_benchy" in argv


def test_perf_argv_with_suite_args():
    argv = build_argv(
        benchmark="throughput_benchy",
        model="qwen3:8b",
        base_url="http://127.0.0.1:11434/v1",
        results_path="/tmp/r.jsonl",
        args={"pp": [2048, 4096], "tg": [256], "concurrency": [1, 4],
              "tokenizer": "Qwen/Qwen3-8B"},
    )
    assert "--pp" in argv
    pp_idx = argv.index("--pp")
    assert argv[pp_idx + 1 : pp_idx + 3] == ["2048", "4096"]
    assert "--tokenizer" in argv
    assert "Qwen/Qwen3-8B" in argv


def test_accuracy_suite_argv():
    argv = build_argv(
        benchmark="context_scaling",
        model="qwen3:8b",
        base_url="http://127.0.0.1:11434",
        results_path="/tmp/r.db",
        args={},
    )
    assert argv[:2] == ["llm-toolkit", "bench"]
    assert "--suite" in argv and "context_scaling" in argv
    assert "--models" in argv and "qwen3:8b" in argv
    assert "--url" in argv and "http://127.0.0.1:11434" in argv


def test_unknown_benchmark_raises():
    import pytest
    with pytest.raises(ValueError, match="unknown benchmark"):
        build_argv(benchmark="not_a_suite", model="m",
                   base_url="x", results_path="y", args={})
