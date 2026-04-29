"""Dataclasses and the RunnerAdapter Protocol for the discovery layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class ModelInfo:
    tag: str
    size_bytes: int | None = None
    modified: float | None = None  # epoch seconds


@dataclass
class LoadedModel:
    tag: str
    vram_bytes: int | None = None
    expires_at: float | None = None  # epoch seconds


@dataclass
class RunnerSnapshot:
    runner: str            # 'ollama' | 'vllm' | 'llama-server'
    base_url: str
    gpu: str | None
    version: str | None
    reachable: bool
    error: str | None
    installed_models: list[ModelInfo] = field(default_factory=list)
    loaded_models: list[LoadedModel] = field(default_factory=list)
    raw: dict = field(default_factory=dict)


class RunnerAdapter(Protocol):
    """All runner adapters implement this interface."""

    name: str

    async def probe(self, base_url: str, gpu: str | None = None) -> RunnerSnapshot:
        ...
