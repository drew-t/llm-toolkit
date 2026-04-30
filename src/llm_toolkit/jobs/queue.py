"""Single-concurrency in-process job queue.

One worker task drains an asyncio.Queue of RunSpecs. While a run is active,
its Broadcaster is registered in `_active` so WS handlers can find it.
"""

from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path

from llm_toolkit.jobs.broadcaster import Broadcaster
from llm_toolkit.jobs.worker import RunSpec, run_subprocess


class JobQueue:
    def __init__(self, *, db_path: Path, runs_dir: Path) -> None:
        self._db_path = db_path
        self._runs_dir = runs_dir
        self._queue: asyncio.Queue[RunSpec] = asyncio.Queue()
        self._active: dict[int, tuple[RunSpec, Broadcaster]] = {}
        self._worker: asyncio.Task | None = None

    async def start(self) -> None:
        if self._worker is not None:
            return
        self._runs_dir.mkdir(parents=True, exist_ok=True)
        self._worker = asyncio.create_task(self._run_loop(), name="job-queue-worker")

    async def stop(self) -> None:
        if self._worker is None:
            return
        self._worker.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._worker
        for spec, _bc in self._active.values():
            spec.cancel_event.set()
        self._worker = None

    async def enqueue(self, spec: RunSpec) -> None:
        await self._queue.put(spec)

    def cancel(self, run_id: int) -> bool:
        entry = self._active.get(run_id)
        if entry is None:
            return False
        spec, _bc = entry
        spec.cancel_event.set()
        return True

    def broadcaster_for(self, run_id: int) -> Broadcaster | None:
        entry = self._active.get(run_id)
        return entry[1] if entry else None

    async def _run_loop(self) -> None:
        while True:
            spec = await self._queue.get()
            bc = Broadcaster()
            self._active[spec.run_id] = (spec, bc)
            try:
                await run_subprocess(spec, db_path=self._db_path, broadcaster=bc)
            finally:
                self._active.pop(spec.run_id, None)
                self._queue.task_done()
