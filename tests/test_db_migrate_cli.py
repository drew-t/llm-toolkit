"""Tests for `llm-toolkit db migrate` JSONL importer."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

from llm_toolkit.bench.runner import async_main
from llm_toolkit.results import BenchResult, JsonlResultStore


def _seed_jsonl(path: Path) -> None:
    store = JsonlResultStore(path)
    store.append(BenchResult(
        benchmark="throughput_benchy",
        model="qwen3:8b",
        timestamp=1700000000.0,
        metrics={"tg_throughput": 114.3},
        metadata={"key": "c1_pp2048_tg128_d0"},
    ))
    store.append(BenchResult(
        benchmark="throughput_benchy",
        model="tmnt-7b-q5",
        timestamp=1700000100.0,
        metrics={"tg_throughput": 142.1},
        metadata={"key": "c1_pp4096_tg128_d0"},
    ))


def _run_cli(argv: list[str]) -> None:
    with patch.object(sys, "argv", ["llm-toolkit", *argv]):
        asyncio.run(async_main())


def test_db_migrate_imports_jsonl_with_backfill(tmp_path: Path):
    src = tmp_path / "old.jsonl"
    db = tmp_path / "results.db"
    _seed_jsonl(src)

    _run_cli([
        "db", "migrate", str(src),
        "--db", str(db),
        "--host", "drubuntu",
        "--runner", "ollama",
        "--gpu", "3080ti",
    ])

    with sqlite3.connect(db) as conn:
        rows = list(
            conn.execute(
                "SELECT benchmark, model, host, runner, gpu, metrics FROM results"
            )
        )
    assert len(rows) == 2
    assert all(r[2] == "drubuntu" and r[3] == "ollama" and r[4] == "3080ti" for r in rows)
    assert json.loads(rows[0][5])["tg_throughput"] in (114.3, 142.1)


def test_db_migrate_no_backfill_leaves_columns_null(tmp_path: Path):
    src = tmp_path / "old.jsonl"
    db = tmp_path / "results.db"
    _seed_jsonl(src)

    _run_cli(["db", "migrate", str(src), "--db", str(db)])

    with sqlite3.connect(db) as conn:
        rows = list(conn.execute("SELECT host, runner, gpu FROM results"))
    assert all(r == (None, None, None) for r in rows)


def test_db_migrate_multiple_files(tmp_path: Path):
    a = tmp_path / "a.jsonl"
    b = tmp_path / "b.jsonl"
    db = tmp_path / "results.db"
    _seed_jsonl(a)
    _seed_jsonl(b)

    _run_cli(["db", "migrate", str(a), str(b), "--db", str(db)])

    with sqlite3.connect(db) as conn:
        n = conn.execute("SELECT COUNT(*) FROM results").fetchone()[0]
    assert n == 4
