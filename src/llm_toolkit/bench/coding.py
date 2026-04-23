"""Coding task benchmark framework.

Defines CodingTask and CodingExecutor for evaluating code generation quality.
The executor is pluggable — consumers provide their own (e.g., pi-agent).
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


class CodingExecutor(Protocol):
    """Protocol for coding task executors."""

    async def run(self, model: str, prompt: str, work_dir: Path, **opts: Any) -> CodingResult: ...


VerifyResult = tuple[float, str, list[dict]]


@dataclass
class CodingTask:
    """A coding benchmark task with prompt, optional fixtures, and verification."""

    key: str
    label: str
    prompt: str
    verify: Callable[[Path], VerifyResult]
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
            score, detail, checks = task.verify(task_dir)
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
