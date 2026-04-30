"""Events streamed from a running job to its WebSocket subscribers."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal

EventType = Literal["log", "status", "result", "finished"]


@dataclass(frozen=True)
class JobEvent:
    type: EventType
    payload: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def log(cls, line: str) -> JobEvent:
        return cls("log", {"line": line})

    @classmethod
    def status(cls, status: str) -> JobEvent:
        return cls("status", {"status": status})

    @classmethod
    def result(
        cls, *, result_id: int, benchmark: str, model: str, metrics: dict[str, Any]
    ) -> JobEvent:
        return cls(
            "result",
            {
                "result_id": result_id,
                "benchmark": benchmark,
                "model": model,
                "metrics": metrics,
            },
        )

    @classmethod
    def finished(cls, status: str, *, exit_code: int | None, results_imported: int) -> JobEvent:
        return cls(
            "finished",
            {
                "status": status,
                "exit_code": exit_code,
                "results_imported": results_imported,
            },
        )

    def to_json(self) -> str:
        return json.dumps({"type": self.type, **self.payload})
