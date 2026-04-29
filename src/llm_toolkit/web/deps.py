"""Dependency-injection helpers for FastAPI handlers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from llm_toolkit.discovery.cache import DiscoveryCache
from llm_toolkit.discovery.hosts import HostsConfig, load_hosts
from llm_toolkit.discovery.llama_server import LlamaServerAdapter
from llm_toolkit.discovery.ollama import OllamaAdapter
from llm_toolkit.discovery.types import RunnerAdapter
from llm_toolkit.discovery.vllm import VLLMAdapter


@dataclass
class AppContext:
    db_path: Path
    hosts_path: Path
    cache: DiscoveryCache
    adapters: dict[str, RunnerAdapter]

    def hosts(self) -> HostsConfig:
        # Re-read on every call so editing hosts.toml is picked up without restart.
        return load_hosts(self.hosts_path)


def make_context(db_path: Path, hosts_path: Path) -> AppContext:
    return AppContext(
        db_path=db_path,
        hosts_path=hosts_path,
        cache=DiscoveryCache(db_path=db_path, ttl_s=10.0),
        adapters={
            "ollama": OllamaAdapter(),
            "vllm": VLLMAdapter(),
            "llama-server": LlamaServerAdapter(),
        },
    )
