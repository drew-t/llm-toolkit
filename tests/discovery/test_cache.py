"""Tests for the TTL cache and snapshot writer."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from llm_toolkit.db import init_db
from llm_toolkit.discovery.cache import DiscoveryCache
from llm_toolkit.discovery.types import RunnerSnapshot


def _snap(host: str, runner: str, gpu: str | None) -> RunnerSnapshot:
    return RunnerSnapshot(
        runner=runner, base_url=f"http://{host}:8080", gpu=gpu,
        version="x", reachable=True, error=None,
    )


@pytest.mark.asyncio
async def test_cache_hits_within_ttl(tmp_path: Path):
    db_path = tmp_path / "r.db"
    init_db(db_path)
    probe = AsyncMock(return_value=_snap("h", "ollama", "3080ti"))

    clock = [1000.0]
    cache = DiscoveryCache(db_path=db_path, ttl_s=10.0, clock=lambda: clock[0])
    s1 = await cache.get("h", "ollama", "http://h:11434", "3080ti", probe)
    clock[0] = 1005.0  # +5s, still inside TTL
    s2 = await cache.get("h", "ollama", "http://h:11434", "3080ti", probe)
    assert s1 is s2
    probe.assert_awaited_once()


@pytest.mark.asyncio
async def test_cache_misses_after_ttl(tmp_path: Path):
    db_path = tmp_path / "r.db"
    init_db(db_path)
    probe = AsyncMock(side_effect=[_snap("h", "ollama", "3080ti"),
                                   _snap("h", "ollama", "3080ti")])

    clock = [1000.0]
    cache = DiscoveryCache(db_path=db_path, ttl_s=10.0, clock=lambda: clock[0])
    await cache.get("h", "ollama", "http://h:11434", "3080ti", probe)
    clock[0] = 1011.0  # +11s, past TTL
    await cache.get("h", "ollama", "http://h:11434", "3080ti", probe)
    assert probe.await_count == 2


@pytest.mark.asyncio
async def test_cache_force_refresh_bypasses_ttl(tmp_path: Path):
    db_path = tmp_path / "r.db"
    init_db(db_path)
    probe = AsyncMock(return_value=_snap("h", "ollama", "3080ti"))

    cache = DiscoveryCache(db_path=db_path, ttl_s=10.0)
    await cache.get("h", "ollama", "http://h:11434", "3080ti", probe)
    await cache.get("h", "ollama", "http://h:11434", "3080ti", probe, force=True)
    assert probe.await_count == 2


@pytest.mark.asyncio
async def test_writes_host_snapshot_row(tmp_path: Path):
    db_path = tmp_path / "r.db"
    init_db(db_path)
    probe = AsyncMock(return_value=_snap("h", "ollama", "3080ti"))

    cache = DiscoveryCache(db_path=db_path, ttl_s=10.0)
    await cache.get("h", "ollama", "http://h:11434", "3080ti", probe)
    with sqlite3.connect(db_path) as conn:
        rows = list(conn.execute(
            "SELECT host, runner, gpu, runner_version, state FROM host_snapshots"
        ))
    assert len(rows) == 1
    assert rows[0][0] == "h" and rows[0][1] == "ollama" and rows[0][2] == "3080ti"
    state = json.loads(rows[0][4])
    assert state["reachable"] is True
