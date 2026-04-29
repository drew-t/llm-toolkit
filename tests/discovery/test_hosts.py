"""Tests for hosts.toml loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from llm_toolkit.discovery.hosts import HostsConfig, RunnerEntry, load_hosts

SAMPLE_TOML = """
[[host]]
name = "drubuntu"

[[host.runner]]
type = "ollama"
url  = "http://drubuntu:11434"
gpu  = "3080ti"

[[host.runner]]
type = "llama-server"
url  = "http://drubuntu:8080"
gpu  = "3080ti"

[[host]]
name = "localhost"

[[host.runner]]
type = "ollama"
url  = "http://127.0.0.1:11434"
gpu  = "m3-max"
"""


def test_load_hosts_parses_two_hosts(tmp_path: Path):
    p = tmp_path / "hosts.toml"
    p.write_text(SAMPLE_TOML)
    cfg = load_hosts(p)
    assert isinstance(cfg, HostsConfig)
    assert [h.name for h in cfg.hosts] == ["drubuntu", "localhost"]
    drubuntu = cfg.hosts[0]
    assert len(drubuntu.runners) == 2
    assert drubuntu.runners[0] == RunnerEntry(
        type="ollama", url="http://drubuntu:11434", gpu="3080ti"
    )


def test_load_hosts_iter_runners(tmp_path: Path):
    p = tmp_path / "hosts.toml"
    p.write_text(SAMPLE_TOML)
    cfg = load_hosts(p)
    triples = [(h, r.type, r.url) for h, r in cfg.iter_runners()]
    assert ("drubuntu", "ollama", "http://drubuntu:11434") in triples
    assert ("localhost", "ollama", "http://127.0.0.1:11434") in triples
    assert len(triples) == 3


def test_load_hosts_missing_file_returns_empty(tmp_path: Path):
    cfg = load_hosts(tmp_path / "nope.toml")
    assert cfg.hosts == []


def test_load_hosts_unknown_runner_type_raises(tmp_path: Path):
    p = tmp_path / "hosts.toml"
    p.write_text(
        '[[host]]\nname = "x"\n'
        '[[host.runner]]\n'
        'type = "weird-thing"\n'
        'url = "http://x:8080"\n'
    )
    with pytest.raises(ValueError, match="weird-thing"):
        load_hosts(p)
