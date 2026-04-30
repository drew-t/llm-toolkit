"""In-process job runner.

Public API:
    JobQueue       — single-concurrency asyncio queue + worker task
    JobEvent       — log/status/result/finished events streamed to WS subscribers
    Broadcaster    — per-run-id pub/sub, used by the WS handlers
"""

__all__ = ["Broadcaster", "JobEvent", "JobQueue"]


def __getattr__(name: str):
    if name == "Broadcaster":
        from llm_toolkit.jobs.broadcaster import Broadcaster

        return Broadcaster
    elif name == "JobEvent":
        from llm_toolkit.jobs.events import JobEvent

        return JobEvent
    elif name == "JobQueue":
        from llm_toolkit.jobs.queue import JobQueue

        return JobQueue
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
