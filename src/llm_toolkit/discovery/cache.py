"""TTL cache for runner snapshots, composed with a SnapshotJournal.

The external interface (`DiscoveryCache.get`) hasn't changed — this is the
seam web routes cross. Internally the class composes two collaborators:

- a private TTL store keyed by (host, runner) — pure in-memory, no I/O
- a `SnapshotJournal` that records every probe result to host_snapshots

Cache hits short-circuit; the journal is only written when a probe actually
runs. Journal failures are observable (raise) rather than silently
swallowed — that was the whole point of separating them.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from pathlib import Path

from llm_toolkit.discovery.snapshot_journal import SnapshotJournal
from llm_toolkit.discovery.types import RunnerSnapshot

ProbeFn = Callable[[str, str | None], Awaitable[RunnerSnapshot]]


class _TTLStore:
    """Private in-memory TTL store keyed by (host, runner). No I/O."""

    def __init__(self, *, ttl_s: float, clock: Callable[[], float]):
        self._ttl_s = ttl_s
        self._clock = clock
        self._entries: dict[tuple[str, str], tuple[float, RunnerSnapshot]] = {}

    def get(self, key: tuple[str, str]) -> RunnerSnapshot | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        ts, snap = entry
        if self._clock() - ts >= self._ttl_s:
            return None
        return snap

    def put(self, key: tuple[str, str], snap: RunnerSnapshot) -> None:
        self._entries[key] = (self._clock(), snap)

    def invalidate(self, host: str | None = None, runner: str | None = None) -> None:
        if host is None and runner is None:
            self._entries.clear()
            return
        for key in list(self._entries):
            if (host is None or key[0] == host) and (runner is None or key[1] == runner):
                del self._entries[key]


class DiscoveryCache:
    """In-memory TTL cache keyed by (host, runner), with journaling on miss."""

    def __init__(
        self,
        *,
        db_path: Path | str,
        ttl_s: float = 10.0,
        clock: Callable[[], float] = time.time,
        journal: SnapshotJournal | None = None,
    ):
        self.db_path = Path(db_path)
        self.ttl_s = ttl_s
        self._store = _TTLStore(ttl_s=ttl_s, clock=clock)
        self._journal = journal or SnapshotJournal(db_path=self.db_path, clock=clock)

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
        key = (host, runner)
        if not force:
            cached = self._store.get(key)
            if cached is not None:
                return cached

        snapshot = await probe(base_url, gpu)
        self._store.put(key, snapshot)
        await self._journal.append(host, snapshot)
        return snapshot

    def invalidate(self, host: str | None = None, runner: str | None = None) -> None:
        self._store.invalidate(host=host, runner=runner)
