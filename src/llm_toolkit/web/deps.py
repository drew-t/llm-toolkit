"""Dependency-injection helpers for FastAPI handlers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from llm_toolkit.discovery.cache import DiscoveryCache
from llm_toolkit.discovery.hosts import HostsConfig, load_hosts
from llm_toolkit.discovery.llama_server import LlamaServerAdapter
from llm_toolkit.discovery.ollama import OllamaAdapter
from llm_toolkit.discovery.types import RunnerAdapter
from llm_toolkit.discovery.vllm import VLLMAdapter
from llm_toolkit.jobs import JobQueue

DEFAULT_RUNS_DIR = Path(
    os.environ.get(
        "LLM_TOOLKIT_RUNS_DIR",
        str(Path.home() / ".local" / "share" / "llm-toolkit" / "runs"),
    )
)


@dataclass
class AppContext:
    db_path: Path
    hosts_path: Path
    runs_dir: Path
    cache: DiscoveryCache
    adapters: dict[str, RunnerAdapter]
    queue: JobQueue

    def hosts(self) -> HostsConfig:
        return load_hosts(self.hosts_path)


def make_context(
    db_path: Path,
    hosts_path: Path,
    runs_dir: Path = DEFAULT_RUNS_DIR,
) -> AppContext:
    runs_dir.mkdir(parents=True, exist_ok=True)
    return AppContext(
        db_path=db_path,
        hosts_path=hosts_path,
        runs_dir=runs_dir,
        cache=DiscoveryCache(db_path=db_path, ttl_s=10.0),
        adapters={
            "ollama": OllamaAdapter(),
            "vllm": VLLMAdapter(),
            "llama-server": LlamaServerAdapter(),
        },
        queue=JobQueue(db_path=db_path, runs_dir=runs_dir),
    )
