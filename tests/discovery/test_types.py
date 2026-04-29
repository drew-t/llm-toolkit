"""Smoke tests for discovery types and the RunnerAdapter Protocol."""

from __future__ import annotations

from llm_toolkit.discovery.types import (
    LoadedModel,
    ModelInfo,
    RunnerAdapter,
    RunnerSnapshot,
)


def test_modelinfo_defaults():
    m = ModelInfo(tag="qwen3:8b")
    assert m.tag == "qwen3:8b"
    assert m.size_bytes is None
    assert m.modified is None


def test_runner_snapshot_defaults():
    s = RunnerSnapshot(
        runner="ollama",
        base_url="http://x:11434",
        gpu="3080ti",
        version="0.5.7",
        reachable=True,
        error=None,
        installed_models=[ModelInfo(tag="a")],
        loaded_models=[LoadedModel(tag="a", vram_bytes=8000000000, expires_at=None)],
        raw={},
    )
    assert s.reachable is True
    assert s.installed_models[0].tag == "a"


def test_runner_adapter_is_a_protocol():
    # Just confirms the Protocol can be referenced at runtime.
    assert RunnerAdapter is not None
