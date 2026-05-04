"""Tests for DiscoveryCache — TTL semantics, journal composition.

The cache composes a private TTL store and a SnapshotJournal. These tests
exercise that composition; the journal's own behavior is covered in
test_snapshot_journal.py.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from llm_toolkit.db import init_db
from llm_toolkit.discovery.cache import DiscoveryCache
from llm_toolkit.discovery.types import RunnerSnapshot


def _snap(host: str = "h", runner: str = "ollama",
          gpu: str | None = "3080ti") -> RunnerSnapshot:
    return RunnerSnapshot(
        runner=runner, base_url=f"http://{host}:8080", gpu=gpu,
        version="x", reachable=True, error=None,
    )


@pytest.mark.asyncio
async def test_cache_hits_within_ttl(tmp_path: Path):
    db_path = tmp_path / "r.db"
    init_db(db_path)
    probe = AsyncMock(return_value=_snap())

    clock = [1000.0]
    cache = DiscoveryCache(db_path=db_path, ttl_s=10.0, clock=lambda: clock[0])
    s1 = await cache.get("h", "ollama", "http://h:11434", "3080ti", probe)
    clock[0] = 1005.0
    s2 = await cache.get("h", "ollama", "http://h:11434", "3080ti", probe)
    assert s1 is s2
    probe.assert_awaited_once()


@pytest.mark.asyncio
async def test_cache_misses_after_ttl(tmp_path: Path):
    db_path = tmp_path / "r.db"
    init_db(db_path)
    probe = AsyncMock(side_effect=[_snap(), _snap()])

    clock = [1000.0]
    cache = DiscoveryCache(db_path=db_path, ttl_s=10.0, clock=lambda: clock[0])
    await cache.get("h", "ollama", "http://h:11434", "3080ti", probe)
    clock[0] = 1011.0
    await cache.get("h", "ollama", "http://h:11434", "3080ti", probe)
    assert probe.await_count == 2


@pytest.mark.asyncio
async def test_cache_force_refresh_bypasses_ttl(tmp_path: Path):
    db_path = tmp_path / "r.db"
    init_db(db_path)
    probe = AsyncMock(return_value=_snap())

    cache = DiscoveryCache(db_path=db_path, ttl_s=10.0)
    await cache.get("h", "ollama", "http://h:11434", "3080ti", probe)
    await cache.get("h", "ollama", "http://h:11434", "3080ti", probe, force=True)
    assert probe.await_count == 2


@pytest.mark.asyncio
async def test_cache_invalidate_clears_all(tmp_path: Path):
    db_path = tmp_path / "r.db"
    init_db(db_path)
    probe = AsyncMock(return_value=_snap())

    cache = DiscoveryCache(db_path=db_path, ttl_s=10.0)
    await cache.get("h", "ollama", "http://h:11434", "3080ti", probe)
    cache.invalidate()
    await cache.get("h", "ollama", "http://h:11434", "3080ti", probe)
    assert probe.await_count == 2


@pytest.mark.asyncio
async def test_cache_invalidate_by_host(tmp_path: Path):
    db_path = tmp_path / "r.db"
    init_db(db_path)
    probe = AsyncMock(return_value=_snap())

    cache = DiscoveryCache(db_path=db_path, ttl_s=10.0)
    await cache.get("h1", "ollama", "http://h1:11434", "3080ti", probe)
    await cache.get("h2", "ollama", "http://h2:11434", "3080ti", probe)
    assert probe.await_count == 2

    cache.invalidate(host="h1")
    await cache.get("h1", "ollama", "http://h1:11434", "3080ti", probe)
    await cache.get("h2", "ollama", "http://h2:11434", "3080ti", probe)
    assert probe.await_count == 3  # only h1 re-probed


@pytest.mark.asyncio
async def test_cache_hit_skips_journal_write(tmp_path: Path):
    """A cache hit short-circuits — the journal is not invoked twice."""
    import sqlite3

    db_path = tmp_path / "r.db"
    init_db(db_path)
    probe = AsyncMock(return_value=_snap())

    cache = DiscoveryCache(db_path=db_path, ttl_s=10.0)
    await cache.get("h", "ollama", "http://h:11434", "3080ti", probe)
    await cache.get("h", "ollama", "http://h:11434", "3080ti", probe)  # cache hit

    with sqlite3.connect(db_path) as conn:
        n = conn.execute("SELECT COUNT(*) FROM host_snapshots").fetchone()[0]
    assert n == 1


@pytest.mark.asyncio
async def test_cache_keeps_entry_when_journal_fails(tmp_path: Path):
    """Journal write failure does not corrupt the in-memory cache."""
    from llm_toolkit.discovery.snapshot_journal import SnapshotJournal

    db_path = tmp_path / "r.db"
    init_db(db_path)
    probe = AsyncMock(return_value=_snap())

    journal = SnapshotJournal(db_path=tmp_path / "missing" / "bad.db")
    cache = DiscoveryCache(db_path=db_path, ttl_s=10.0, journal=journal)

    # First call: probe runs; journal fails (raises). The in-memory cache must
    # still hold the snapshot so we don't re-probe storms on every request.
    import sqlite3
    with pytest.raises(sqlite3.OperationalError):
        await cache.get("h", "ollama", "http://h:11434", "3080ti", probe)

    # Swap journal to a working one; second call must still come from cache.
    cache._journal = SnapshotJournal(db_path=db_path)
    s = await cache.get("h", "ollama", "http://h:11434", "3080ti", probe)
    assert s.reachable is True
    probe.assert_awaited_once()
