"""Tests for db schema and connection helper."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from llm_toolkit.db import DEFAULT_DB_PATH, connect, init_db


def test_init_db_creates_tables(tmp_path: Path):
    db_path = tmp_path / "results.db"
    init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    assert {"results", "runs", "host_snapshots"} <= names


def test_init_db_is_idempotent(tmp_path: Path):
    db_path = tmp_path / "results.db"
    init_db(db_path)
    init_db(db_path)  # second call must not raise
    with sqlite3.connect(db_path) as conn:
        rows = list(
            conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' "
                "AND name='idx_results_timestamp'"
            )
        )
    assert len(rows) == 1


def test_connect_returns_wal_mode(tmp_path: Path):
    db_path = tmp_path / "results.db"
    init_db(db_path)
    with connect(db_path) as conn:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"


def test_default_db_path_is_under_local_share():
    assert "llm-toolkit" in str(DEFAULT_DB_PATH)
    assert str(DEFAULT_DB_PATH).endswith("results.db")
