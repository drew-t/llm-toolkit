"""Append-only journal for runner snapshots.

Writes one row per probe result into the `host_snapshots` table. The write
is dispatched to a background thread so the async event loop stays
responsive — sqlite3 is blocking. Failures bubble up rather than being
swallowed; the cache treats journal failure as a real error.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import time
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path

from llm_toolkit.discovery.types import RunnerSnapshot


class SnapshotJournal:
    """Append-only writer to the host_snapshots table."""

    def __init__(
        self,
        *,
        db_path: Path | str,
        clock: Callable[[], float] = time.time,
    ):
        self.db_path = Path(db_path)
        self._clock = clock

    async def append(self, host: str, snap: RunnerSnapshot) -> None:
        """Write one snapshot row. Awaitable so callers don't block the loop."""
        timestamp = self._clock()
        await asyncio.to_thread(self._write_row, host, snap, timestamp)

    def _write_row(self, host: str, snap: RunnerSnapshot, timestamp: float) -> None:
        state = {
            "reachable": snap.reachable,
            "error": snap.error,
            "installed_models": [asdict(m) for m in snap.installed_models],
            "loaded_models": [asdict(m) for m in snap.loaded_models],
            "raw": snap.raw,
        }
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO host_snapshots "
                "(host, runner, gpu, runner_version, timestamp, state, config_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (host, snap.runner, snap.gpu, snap.version, timestamp,
                 json.dumps(state), None),
            )
            conn.commit()
