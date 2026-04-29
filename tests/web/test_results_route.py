"""Tests for /api/results."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from llm_toolkit.results import BenchResult, SqliteResultStore
from llm_toolkit.web.app import create_app


def _seed(db_path: Path) -> None:
    store = SqliteResultStore(db_path)
    store.append(BenchResult(
        benchmark="throughput_benchy", model="qwen3:8b",
        timestamp=1000.0,
        metrics={"tg_throughput": 114.3, "pp_throughput": 3923.0},
        metadata={"host": "drubuntu", "runner": "ollama", "gpu": "3080ti"},
    ))
    store.append(BenchResult(
        benchmark="throughput_benchy", model="qwen3:8b",
        timestamp=2000.0,
        metrics={"tg_throughput": 142.1, "pp_throughput": 9421.0},
        metadata={"host": "drubuntu", "runner": "llama-server", "gpu": "3080ti"},
    ))
    store.append(BenchResult(
        benchmark="context_scaling", model="qwen3:8b",
        timestamp=3000.0,
        metrics={"score": 0.91},
        metadata={"host": "localhost", "runner": "ollama", "gpu": "m3-max"},
    ))


def _client(tmp_path: Path) -> TestClient:
    db = tmp_path / "r.db"
    _seed(db)
    return TestClient(create_app(db_path=db, hosts_path=tmp_path / "hosts.toml"))


def test_list_default_sort_desc(tmp_path: Path):
    r = _client(tmp_path).get("/api/results")
    assert r.status_code == 200
    body = r.json()
    assert [row["timestamp"] for row in body["results"]] == [3000.0, 2000.0, 1000.0]


def test_filter_by_runner(tmp_path: Path):
    r = _client(tmp_path).get("/api/results?runner=llama-server")
    assert [row["metrics"]["tg_throughput"] for row in r.json()["results"]] == [142.1]


def test_filter_by_benchmark_and_host(tmp_path: Path):
    r = _client(tmp_path).get("/api/results?benchmark=throughput_benchy&host=drubuntu")
    assert len(r.json()["results"]) == 2


def test_get_single_result(tmp_path: Path):
    client = _client(tmp_path)
    listing = client.get("/api/results").json()["results"]
    rid = listing[0]["id"]
    r = client.get(f"/api/results/{rid}")
    assert r.status_code == 200
    assert r.json()["id"] == rid


def test_compare_returns_baseline_diffs(tmp_path: Path):
    client = _client(tmp_path)
    listing = client.get("/api/results?benchmark=throughput_benchy").json()["results"]
    ids = [row["id"] for row in listing]
    r = client.post("/api/results/compare", json={"ids": ids})
    assert r.status_code == 200
    body = r.json()
    assert len(body["rows"]) == 2
    assert body["primary_metric"] == "tg_throughput"
    # Whichever row was first becomes the baseline (diff_pct == 0)
    diffs = [row["diff_pct"] for row in body["rows"]]
    assert 0.0 in diffs
