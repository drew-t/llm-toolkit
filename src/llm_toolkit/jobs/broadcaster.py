"""Per-run-id event fan-out used by /ws/runs/<id> handlers."""

from __future__ import annotations

import asyncio
import contextlib

from llm_toolkit.jobs.events import JobEvent


class Broadcaster:
    def __init__(self, max_queue: int = 1024) -> None:
        self._subs: list[asyncio.Queue[JobEvent | None]] = []
        self._max_queue = max_queue
        self._closed = False

    def subscribe(self) -> asyncio.Queue[JobEvent | None]:
        q: asyncio.Queue[JobEvent | None] = asyncio.Queue(self._max_queue)
        self._subs.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[JobEvent | None]) -> None:
        with contextlib.suppress(ValueError):
            self._subs.remove(q)

    async def publish(self, event: JobEvent) -> None:
        for q in list(self._subs):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                self.unsubscribe(q)

    async def close(self) -> None:
        self._closed = True
        for q in list(self._subs):
            try:
                q.put_nowait(None)
            except asyncio.QueueFull:
                self.unsubscribe(q)
