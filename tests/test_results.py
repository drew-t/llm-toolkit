"""Tests for the JSONL result store and the read_jsonl helper.

JsonlResultStore is now narrowed to append-only. The migration path uses
the module-level read_jsonl(path) helper. Querying and summary tables
live on SqliteResultStore.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from llm_toolkit.results import BenchResult, JsonlResultStore, ResultStore, read_jsonl


def test_bench_result_creation():
    r = BenchResult(
        benchmark="test_suite", model="qwen3:14b", timestamp=time.time(),
        metrics={"wall_time_s": 1.5, "decode_tok_s": 50.0}, metadata={"tier": 1000},
    )
    assert r.benchmark == "test_suite"
    assert r.metrics["wall_time_s"] == 1.5


def test_jsonl_store_append_persists(tmp_path: Path):
    path = tmp_path / "results.jsonl"
    store = JsonlResultStore(path)
    store.append(BenchResult("s", "m", 1.0, {"x": 1}, {}))
    store.append(BenchResult("s", "m", 2.0, {"x": 2}, {}))
    rows = read_jsonl(path)
    assert [r.metrics["x"] for r in rows] == [1, 2]


def test_jsonl_store_no_query_or_summary_table():
    """Public surface of JsonlResultStore is append() only."""
    store = JsonlResultStore("/tmp/dummy.jsonl")
    assert not hasattr(store, "query")
    assert not hasattr(store, "summary_table")


def test_read_jsonl_missing_file_returns_empty(tmp_path: Path):
    assert read_jsonl(tmp_path / "absent.jsonl") == []


def test_read_jsonl_skips_blank_lines(tmp_path: Path):
    path = tmp_path / "r.jsonl"
    path.write_text(
        '{"benchmark": "s", "model": "m", "timestamp": 1.0, "metrics": {}, "metadata": {}}\n'
        "\n"
        '{"benchmark": "s", "model": "m", "timestamp": 2.0, "metrics": {}, "metadata": {}}\n'
    )
    rows = read_jsonl(path)
    assert len(rows) == 2


def test_factory_jsonl_extension_returns_writer(tmp_path: Path):
    """ResultStore(path.jsonl) keeps working — TMNT relies on append()."""
    store = ResultStore(tmp_path / "out.jsonl")
    store.append(BenchResult("s", "m", time.time(), {}, {}))
    assert (tmp_path / "out.jsonl").exists()


def test_factory_non_jsonl_returns_sqlite(tmp_path: Path):
    """Anything else routes to SQLite."""
    from llm_toolkit.results import SqliteResultStore
    store = ResultStore(tmp_path / "out.db")
    assert isinstance(store, SqliteResultStore)


def test_jsonl_store_query_removed_in_favor_of_read_jsonl(tmp_path: Path):
    """If anyone was calling .query() on a JSONL store, we want a clear failure."""
    store = JsonlResultStore(tmp_path / "x.jsonl")
    with pytest.raises(AttributeError):
        store.query()  # type: ignore[attr-defined]
