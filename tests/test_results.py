"""Tests for the JSONL result store."""

from __future__ import annotations

import time

from llm_toolkit.results import BenchResult, ResultStore


def test_bench_result_creation():
    r = BenchResult(
        benchmark="test_suite", model="qwen3:14b", timestamp=time.time(),
        metrics={"wall_time_s": 1.5, "decode_tok_s": 50.0}, metadata={"tier": 1000},
    )
    assert r.benchmark == "test_suite"
    assert r.metrics["wall_time_s"] == 1.5


def test_result_store_append_and_query(tmp_path):
    store = ResultStore(tmp_path / "results.jsonl")
    now = time.time()
    store.append(BenchResult("suite_a", "model_1", now, {"score": 0.9}, {}))
    store.append(BenchResult("suite_b", "model_1", now, {"score": 0.8}, {}))
    store.append(BenchResult("suite_a", "model_2", now, {"score": 0.7}, {}))
    all_results = store.query()
    assert len(all_results) == 3
    suite_a = store.query(benchmark="suite_a")
    assert len(suite_a) == 2
    model_1 = store.query(model="model_1")
    assert len(model_1) == 2


def test_result_store_query_since(tmp_path):
    store = ResultStore(tmp_path / "results.jsonl")
    old = time.time() - 3600
    recent = time.time()
    store.append(BenchResult("s", "m", old, {}, {}))
    store.append(BenchResult("s", "m", recent, {}, {}))
    results = store.query(since=recent - 1)
    assert len(results) == 1


def test_result_store_empty(tmp_path):
    store = ResultStore(tmp_path / "results.jsonl")
    assert store.query() == []


def test_result_store_summary_table(tmp_path):
    store = ResultStore(tmp_path / "results.jsonl")
    now = time.time()
    results = [
        BenchResult("suite", "model_a", now, {"wall_time_s": 1.0}, {}),
        BenchResult("suite", "model_b", now, {"wall_time_s": 2.0}, {}),
    ]
    table = store.summary_table(results, pivot="model", metric="wall_time_s")
    assert "model_a" in table
    assert "model_b" in table


def test_result_store_persistence(tmp_path):
    path = tmp_path / "results.jsonl"
    store1 = ResultStore(path)
    store1.append(BenchResult("s", "m", time.time(), {"x": 1}, {}))
    store2 = ResultStore(path)
    assert len(store2.query()) == 1
