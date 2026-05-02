"""Coding task benchmark framework.

Defines CodingTask and CodingExecutor for evaluating code generation quality.
The executor is pluggable — consumers provide their own (e.g., pi-agent).

Verification used to see only the filesystem the executor left behind. Now
the executor produces a structured `trace` of events (tool calls, tool
results, agent text) and `verify` receives both the work directory *and*
the full `CodingResult`. This lets verifiers reject behavior that wouldn't
show up in filesystem state — e.g. "any task that called the shell tool".
"""

from __future__ import annotations

import shutil
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass
class TraceEvent:
    """One event in an executor's structured log.

    `kind` is conventionally one of "tool_call", "tool_result", "text",
    "error" — but executors can emit any string. `payload` carries the
    event-specific data (e.g. tool name + input for tool_call).
    """

    kind: str
    payload: dict = field(default_factory=dict)
    timestamp: float | None = None


@dataclass
class CodingResult:
    """Result from a coding executor run."""

    wall_time_s: float
    exit_code: int
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    tool_calls: int = 0
    turns: int = 0
    response_text: str = ""
    error: str | None = None
    trace: list[TraceEvent] = field(default_factory=list)


class CodingExecutor(Protocol):
    """Protocol for coding task executors."""

    async def run(self, model: str, prompt: str, work_dir: Path, **opts: Any) -> CodingResult: ...


VerifyResult = tuple[float, str, list[dict]]
VerifyFn = Callable[[Path, CodingResult], VerifyResult]


@dataclass
class CodingTask:
    """A coding benchmark task with prompt, optional fixtures, and verification.

    `verify` receives the work directory and the full executor result so it
    can inspect the trace alongside filesystem state.
    """

    key: str
    label: str
    prompt: str
    verify: VerifyFn
    setup: Callable[[Path], None] | None = None
    fixtures: dict[str, str] = field(default_factory=dict)


def setup_task_dir(task: CodingTask) -> Path:
    task_dir = Path(tempfile.mkdtemp(prefix=f"llm_bench_{task.key}_"))
    for filename, content in task.fixtures.items():
        (task_dir / filename).write_text(content)
    if task.setup:
        task.setup(task_dir)
    return task_dir


def cleanup_task_dir(task_dir: Path) -> None:
    shutil.rmtree(task_dir, ignore_errors=True)


async def run_coding_benchmark(
    executor: CodingExecutor,
    model: str,
    tasks: list[CodingTask],
    **executor_opts: Any,
) -> list[dict]:
    results = []
    for task in tasks:
        task_dir = setup_task_dir(task)
        try:
            exec_result = await executor.run(model, task.prompt, task_dir, **executor_opts)
            score, detail, checks = task.verify(task_dir, exec_result)
            results.append(
                {
                    "benchmark": "coding_tasks",
                    "model": model,
                    "task": task.key,
                    "task_label": task.label,
                    "wall_time_s": exec_result.wall_time_s,
                    "correctness": score,
                    "checks_detail": detail,
                    "checks": checks,
                    "total_input_tokens": exec_result.total_input_tokens,
                    "total_output_tokens": exec_result.total_output_tokens,
                    "tool_calls": exec_result.tool_calls,
                    "turns": exec_result.turns,
                    "exit_code": exec_result.exit_code,
                    "error": exec_result.error,
                    "timestamp": time.time(),
                }
            )
        except Exception as e:
            results.append(
                {
                    "benchmark": "coding_tasks",
                    "model": model,
                    "task": task.key,
                    "task_label": task.label,
                    "error": str(e),
                    "correctness": 0.0,
                    "timestamp": time.time(),
                }
            )
        finally:
            cleanup_task_dir(task_dir)
    return results
