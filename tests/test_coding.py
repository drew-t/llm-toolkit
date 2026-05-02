"""Tests for the coding task benchmark framework."""

from __future__ import annotations

import asyncio
from pathlib import Path

from llm_toolkit.bench.coding import (
    CodingResult,
    CodingTask,
    TraceEvent,
    run_coding_benchmark,
)


class MockExecutor:
    def __init__(self, trace: list[TraceEvent] | None = None):
        self._trace = trace or []

    async def run(self, model: str, prompt: str, work_dir: Path, **opts) -> CodingResult:
        return CodingResult(
            wall_time_s=1.0,
            exit_code=0,
            total_input_tokens=100,
            total_output_tokens=50,
            tool_calls=2,
            turns=1,
            trace=self._trace,
        )


def _verify_always_pass(cwd: Path, result: CodingResult) -> tuple[float, str, list[dict]]:
    return 1.0, "all checks passed", [{"name": "exists", "passed": True}]


def _verify_always_fail(cwd: Path, result: CodingResult) -> tuple[float, str, list[dict]]:
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
    dummy_result = CodingResult(wall_time_s=0.0, exit_code=0)
    score, _detail, checks = task.verify(Path("/tmp"), dummy_result)
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


def test_trace_event_construction():
    e = TraceEvent(kind="tool_call", payload={"name": "edit", "input": {"path": "x"}})
    assert e.kind == "tool_call"
    assert e.payload["name"] == "edit"


def test_verify_can_inspect_trace():
    """Verifiers may use the executor's trace, not just filesystem state."""
    executor = MockExecutor(trace=[
        TraceEvent(kind="tool_call", payload={"name": "edit"}),
        TraceEvent(kind="tool_call", payload={"name": "shell"}),
    ])

    def reject_shell(cwd: Path, r: CodingResult) -> tuple[float, str, list[dict]]:
        used_shell = any(e.kind == "tool_call" and e.payload.get("name") == "shell"
                         for e in r.trace)
        return (0.0 if used_shell else 1.0,
                "shell not allowed" if used_shell else "ok",
                [{"name": "no_shell", "passed": not used_shell}])

    task = CodingTask(key="t1", label="t", prompt="p", verify=reject_shell)
    results = asyncio.run(run_coding_benchmark(executor, "m", [task]))
    assert results[0]["correctness"] == 0.0
    assert results[0]["checks"][0]["name"] == "no_shell"


def test_verify_ignoring_trace_still_works():
    """A verifier that only takes (cwd, result) and ignores trace must work."""
    executor = MockExecutor(trace=[TraceEvent(kind="tool_call", payload={})])
    task = CodingTask(key="t1", label="t", prompt="p", verify=_verify_always_pass)
    results = asyncio.run(run_coding_benchmark(executor, "m", [task]))
    assert results[0]["correctness"] == 1.0


def test_coding_result_trace_defaults_empty():
    r = CodingResult(wall_time_s=1.0, exit_code=0)
    assert r.trace == []
