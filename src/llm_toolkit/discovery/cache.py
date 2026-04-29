"""TTL cache for runner snapshots, with persistence to host_snapshots."""

from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Awaitable, Callable
from dataclasses import asdict
from pathlib import Path

from llm_toolkit.discovery.types import RunnerSnapshot

ProbeFn = Callable[[str, str | None], Awaitable[RunnerSnapshot]]


class DiscoveryCache:
    """In-memory TTL cache keyed by (host, runner). Persists every probe to host_snapshots."""

    def __init__(
        self,
        *,
        db_path: Path | str,
        ttl_s: float = 10.0,
        clock: Callable[[], float] = time.time,
    ):
        self.db_path = Path(db_path)
        self.ttl_s = ttl_s
        self._clock = clock
        self._cache: dict[tuple[str, str], tuple[float, RunnerSnapshot]] = {}

    async def get(
        self,
        host: str,
        runner: str,
        base_url: str,
        gpu: str | None,
        probe: ProbeFn,
        *,
        force: bool = False,
    ) -> RunnerSnapshot:
        now = self._clock()
        key = (host, runner)
        if not force and key in self._cache:
            ts, snap = self._cache[key]
            if now - ts < self.ttl_s:
                return snap

        snapshot = await probe(base_url, gpu)
        self._cache[key] = (now, snapshot)
        self._persist(host, snapshot)
        return snapshot

    def invalidate(self, host: str | None = None, runner: str | None = None) -> None:
        if host is None and runner is None:
            self._cache.clear()
            return
        for key in list(self._cache):
            if (host is None or key[0] == host) and (runner is None or key[1] == runner):
                del self._cache[key]

    def _persist(self, host: str, snap: RunnerSnapshot) -> None:
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
                (host, snap.runner, snap.gpu, snap.version, self._clock(),
                 json.dumps(state), None),
            )
            conn.commit()
