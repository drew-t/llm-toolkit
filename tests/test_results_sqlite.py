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
    """When metadata contains host/runner/gpu, they get hoisted to columns."""
    import sqlite3
    store = SqliteResultStore(tmp_path / "r.db")
    store.append(_result())
    with sqlite3.connect(tmp_path / "r.db") as conn:
        row = conn.execute(
            "SELECT host, runner, gpu FROM results"
        ).fetchone()
    assert row == ("drubuntu", "ollama", "3080ti")


def test_factory_returns_jsonl_for_jsonl_path(tmp_path: Path):
    store = ResultStore(tmp_path / "out.jsonl")
    assert isinstance(store, JsonlResultStore)


def test_factory_returns_sqlite_for_db_path(tmp_path: Path):
    store = ResultStore(tmp_path / "out.db")
    assert isinstance(store, SqliteResultStore)


def test_jsonl_store_still_works(tmp_path: Path):
    store = JsonlResultStore(tmp_path / "out.jsonl")
    store.append(_result())
    rows = store.query()
    assert rows[0].model == "qwen3:8b"
