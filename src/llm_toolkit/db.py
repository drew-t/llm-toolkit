"""SQLite schema, connection helper, and init for llm-toolkit's result store."""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

DEFAULT_DB_PATH = Path(
    os.environ.get(
        "LLM_TOOLKIT_DB",
        str(Path.home() / ".local" / "share" / "llm-toolkit" / "results.db"),
    )
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS results (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  benchmark   TEXT NOT NULL,
  model       TEXT NOT NULL,
  host        TEXT,
  runner      TEXT,
  gpu         TEXT,
  run_id      INTEGER,
  timestamp   REAL NOT NULL,
  metrics     TEXT NOT NULL,
  metadata    TEXT NOT NULL,
  FOREIGN KEY(run_id) REFERENCES runs(id)
);

CREATE TABLE IF NOT EXISTS runs (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  status          TEXT NOT NULL,
  benchmark       TEXT NOT NULL,
  model           TEXT NOT NULL,
  host            TEXT,
  runner          TEXT,
  gpu             TEXT,
  runner_version  TEXT,
  args_json       TEXT NOT NULL,
  config_json     TEXT,
  started_at      REAL,
  finished_at     REAL,
  exit_code       INTEGER,
  log_path        TEXT
);

CREATE TABLE IF NOT EXISTS host_snapshots (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  host            TEXT NOT NULL,
  runner          TEXT NOT NULL,
  gpu             TEXT,
  runner_version  TEXT,
  timestamp       REAL NOT NULL,
  state           TEXT NOT NULL,
  config_json     TEXT
);

CREATE INDEX IF NOT EXISTS idx_results_bench_model ON results(benchmark, model);
CREATE INDEX IF NOT EXISTS idx_results_timestamp   ON results(timestamp);
CREATE INDEX IF NOT EXISTS idx_results_host_runner ON results(host, runner);
CREATE INDEX IF NOT EXISTS idx_results_host_gpu    ON results(host, gpu);
CREATE INDEX IF NOT EXISTS idx_snapshots_host_ts   ON host_snapshots(host, timestamp);
"""


def init_db(db_path: Path | str = DEFAULT_DB_PATH) -> None:
    """Create the database file (if missing) and ensure the schema is present."""
    p = Path(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(p) as conn:
        conn.executescript(SCHEMA)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.commit()


@contextmanager
def connect(db_path: Path | str = DEFAULT_DB_PATH) -> Iterator[sqlite3.Connection]:
    """Open a connection. Caller is responsible for transactions/commits."""
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
    finally:
        conn.close()
