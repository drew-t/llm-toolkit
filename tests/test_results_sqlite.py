"""Tests for SqliteResultStore and the ResultStore factory."""

from __future__ import annotations

from pathlib import Path

from llm_toolkit.results import (
    BenchResult,
    JsonlResultStore,
    ResultStore,
    SqliteResultStore,
)


def _result(benchmark: str = "throughput_benchy", model: str = "qwen3:8b") -> BenchResult:
    return BenchResult(
        benchmark=benchmark,
        model=model,
        timestamp=1700000000.0,
        metrics={"tg_throughput": 114.3, "pp_throughput": 3923.0},
        metadata={"key": "c1_pp2048_tg128_d0", "host": "drubuntu",
                  "runner": "ollama", "gpu": "3080ti"},
    )


def test_sqlite_store_append_and_query(tmp_path: Path):
    store = SqliteResultStore(tmp_path / "r.db")
    store.append(_result(model="a"))
    store.append(_result(model="b"))
    rows = store.query()
    assert {r.model for r in rows} == {"a", "b"}
    assert rows[0].metrics["tg_throughput"] == 114.3


def test_sqlite_store_query_filters(tmp_path: Path):
    store = SqliteResultStore(tmp_path / "r.db")
    store.append(_result(model="a"))
    store.append(_result(model="b"))
    store.append(_result(model="b", benchmark="context_scaling"))
    rows = store.query(model="b", benchmark="throughput_benchy")
    assert len(rows) == 1


def test_sqlite_store_extracts_host_runner_gpu_from_metadata(tmp_path: Path):
    """When metadata contains host/runner/gpu/run_id, they get hoisted to columns."""
    import sqlite3
    store = SqliteResultStore(tmp_path / "r.db")
    r = _result()
    r.metadata = {**r.metadata, "run_id": 42}
    store.append(r)
    with sqlite3.connect(tmp_path / "r.db") as conn:
        row = conn.execute(
            "SELECT host, runner, gpu, run_id FROM results"
        ).fetchone()
    assert row == ("drubuntu", "ollama", "3080ti", 42)


def test_sqlite_store_orders_desc_and_filters_since(tmp_path: Path):
    store = SqliteResultStore(tmp_path / "r.db")
    old = BenchResult("throughput_benchy", "m", 1000.0, {"x": 1}, {})
    new = BenchResult("throughput_benchy", "m", 2000.0, {"x": 2}, {})
    store.append(old)
    store.append(new)
    rows = store.query()
    assert [r.timestamp for r in rows] == [2000.0, 1000.0]
    assert store.query(since=1500.0) == [new]


def test_sqlite_store_limit(tmp_path: Path):
    store = SqliteResultStore(tmp_path / "r.db")
    for i in range(5):
        store.append(BenchResult("b", "m", float(i), {}, {}))
    assert len(store.query(limit=2)) == 2


def test_sqlite_store_summary_table(tmp_path: Path):
    store = SqliteResultStore(tmp_path / "r.db")
    store.append(BenchResult("suite", "model_a", 1.0, {"wall_time_s": 1.0}, {}))
    store.append(BenchResult("suite", "model_b", 2.0, {"wall_time_s": 2.0}, {}))
    rows = store.query()
    table = store.summary_table(rows, pivot="model", metric="wall_time_s")
    assert "model_a" in table
    assert "model_b" in table


def test_factory_returns_jsonl_for_jsonl_path(tmp_path: Path):
    store = ResultStore(tmp_path / "out.jsonl")
    assert isinstance(store, JsonlResultStore)


def test_factory_returns_sqlite_for_db_path(tmp_path: Path):
    store = ResultStore(tmp_path / "out.db")
    assert isinstance(store, SqliteResultStore)
