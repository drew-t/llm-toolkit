"""Tests for the discovery snapshot journal — append-only writes to host_snapshots."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path

import pytest

from llm_toolkit.db import init_db
from llm_toolkit.discovery.snapshot_journal import SnapshotJournal
from llm_toolkit.discovery.types import RunnerSnapshot


def _snap(host: str = "h", runner: str = "ollama", gpu: str | None = "3080ti") -> RunnerSnapshot:
    return RunnerSnapshot(
        runner=runner, base_url=f"http://{host}:8080", gpu=gpu,
        version="x", reachable=True, error=None,
    )


@pytest.mark.asyncio
async def test_append_writes_host_snapshot_row(tmp_path: Path):
    db_path = tmp_path / "r.db"
    init_db(db_path)
    journal = SnapshotJournal(db_path=db_path)

    await journal.append("h", _snap())

    with sqlite3.connect(db_path) as conn:
        rows = list(conn.execute(
            "SELECT host, runner, gpu, runner_version, state FROM host_snapshots"
        ))
    assert len(rows) == 1
    assert rows[0][0] == "h" and rows[0][1] == "ollama" and rows[0][2] == "3080ti"
    state = json.loads(rows[0][4])
    assert state["reachable"] is True


@pytest.mark.asyncio
async def test_append_does_not_block_event_loop(tmp_path: Path):
    """Journal writes go through asyncio.to_thread; the loop stays responsive."""
    db_path = tmp_path / "r.db"
    init_db(db_path)
    journal = SnapshotJournal(db_path=db_path)

    # Heartbeat task that should keep ticking while we append.
    ticks = 0

    async def heartbeat():
        nonlocal ticks
        for _ in range(5):
            await asyncio.sleep(0)
            ticks += 1

    await asyncio.gather(journal.append("h", _snap()), heartbeat())
    assert ticks == 5


@pytest.mark.asyncio
async def test_append_failure_is_observable(tmp_path: Path):
    """A bad DB path raises rather than silently swallowing the write."""
    journal = SnapshotJournal(db_path=tmp_path / "does_not_exist" / "x.db")
    with pytest.raises(sqlite3.OperationalError):
        await journal.append("h", _snap())


@pytest.mark.asyncio
async def test_append_serializes_loaded_and_installed_models(tmp_path: Path):
    from llm_toolkit.discovery.types import LoadedModel, ModelInfo
    db_path = tmp_path / "r.db"
    init_db(db_path)
    journal = SnapshotJournal(db_path=db_path)

    snap = RunnerSnapshot(
        runner="ollama", base_url="http://h:11434", gpu=None,
        version="0.5", reachable=True, error=None,
        installed_models=[ModelInfo(tag="qwen3:8b", size_bytes=4_000_000_000)],
        loaded_models=[LoadedModel(tag="qwen3:8b", vram_bytes=4_000_000_000)],
    )
    await journal.append("h", snap)

    with sqlite3.connect(db_path) as conn:
        state = json.loads(conn.execute(
            "SELECT state FROM host_snapshots"
        ).fetchone()[0])
    assert state["installed_models"][0]["tag"] == "qwen3:8b"
    assert state["loaded_models"][0]["tag"] == "qwen3:8b"
