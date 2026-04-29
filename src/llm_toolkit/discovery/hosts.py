"""hosts.toml loader for the discovery layer."""

from __future__ import annotations

import os
import tomllib
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

KNOWN_RUNNERS = {"ollama", "vllm", "llama-server"}

DEFAULT_HOSTS_PATH = Path(
    os.environ.get(
        "LLM_TOOLKIT_HOSTS",
        str(Path.home() / ".config" / "llm-toolkit" / "hosts.toml"),
    )
)


@dataclass(frozen=True)
class RunnerEntry:
    type: str            # 'ollama' | 'vllm' | 'llama-server'
    url: str
    gpu: str | None = None


@dataclass
class HostEntry:
    name: str
    runners: list[RunnerEntry] = field(default_factory=list)


@dataclass
class HostsConfig:
    hosts: list[HostEntry] = field(default_factory=list)

    def iter_runners(self) -> Iterator[tuple[str, RunnerEntry]]:
        """Yield (host_name, runner_entry) for every configured runner."""
        for host in self.hosts:
            for runner in host.runners:
                yield host.name, runner


def load_hosts(path: Path | str = DEFAULT_HOSTS_PATH) -> HostsConfig:
    """Load hosts.toml. Returns an empty config if the file does not exist."""
    p = Path(path)
    if not p.exists():
        return HostsConfig()
    with p.open("rb") as f:
        data = tomllib.load(f)

    hosts: list[HostEntry] = []
    for host_block in data.get("host", []):
        runners: list[RunnerEntry] = []
        for r in host_block.get("runner", []):
            rtype = r["type"]
            if rtype not in KNOWN_RUNNERS:
                raise ValueError(
                    f"Unknown runner type {rtype!r} in {p}. "
                    f"Known: {sorted(KNOWN_RUNNERS)}"
                )
            runners.append(RunnerEntry(type=rtype, url=r["url"], gpu=r.get("gpu")))
        hosts.append(HostEntry(name=host_block["name"], runners=runners))
    return HostsConfig(hosts=hosts)
