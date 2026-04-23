"""Tests for the coding task benchmark framework."""

from __future__ import annotations

import asyncio
from pathlib import Path

from llm_toolkit.bench.coding import (
    CodingResult,
    CodingTask,
    run_coding_benchmark,
)


class MockExecutor:
    async def run(self, model: str, prompt: str, work_dir: Path, **opts) -> CodingResult:
        return CodingResult(
            wall_time_s=1.0,
            exit_code=0,
            total_input_tokens=100,
            total_output_tokens=50,
            tool_calls=2,
            turns=1,
        )


def _verify_always_pass(cwd: Path) -> tuple[float, str, list[dict]]:
    return 1.0, "all checks passed", [{"name": "exists", "passed": True}]


def _verify_always_fail(cwd: Path) -> tuple[float, str, list[dict]]:
    return 0.0, "file not found", [{"name": "exists", "passed": False}]


def test_coding_task_creation():
    task = CodingTask(
        key="t1", label="Hello World", prompt="Create hello.py", verify=_verify_always_pass
    )
    assert task.key == "t1"


def test_coding_task_verify():
    task = CodingTask(
        key="t1", label="Hello World", prompt="Create hello.py", verify=_verify_always_pass
    )
    score, _detail, checks = task.verify(Path("/tmp"))
    assert score == 1.0
    assert checks[0]["passed"] is True


def test_run_coding_benchmark():
    executor = MockExecutor()
    tasks = [
        CodingTask(key="t1", label="Test 1", prompt="do thing", verify=_verify_always_pass),
        CodingTask(key="t2", label="Test 2", prompt="do other", verify=_verify_always_fail),
    ]
    results = asyncio.run(run_coding_benchmark(executor, "test-model", tasks))
    assert len(results) == 2
    assert results[0]["correctness"] == 1.0
    assert results[1]["correctness"] == 0.0
