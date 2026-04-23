"""Tests for the experiment training harness (config only — no GPU required)."""

from __future__ import annotations

from pathlib import Path

from llm_toolkit.train.experiment import ExperimentConfig, load_jsonl


def test_experiment_config():
    cfg = ExperimentConfig(
        name="test_experiment",
        train_data=Path("/tmp/train.jsonl"),
        output_dir=Path("/tmp/output"),
        epochs=5,
        batch_size=16,
    )
    assert cfg.name == "test_experiment"
    assert cfg.epochs == 5


def test_load_jsonl(tmp_path):
    data = tmp_path / "data.jsonl"
    data.write_text('{"input": "hello", "label": "world"}\n{"input": "foo", "label": "bar"}\n')
    examples = load_jsonl(data)
    assert len(examples) == 2
    assert examples[0]["input"] == "hello"


def test_load_jsonl_empty(tmp_path):
    data = tmp_path / "empty.jsonl"
    data.write_text("")
    examples = load_jsonl(data)
    assert examples == []


def test_load_jsonl_with_blanks(tmp_path):
    data = tmp_path / "data.jsonl"
    data.write_text('{"x": 1}\n\n{"x": 2}\n  \n')
    examples = load_jsonl(data)
    assert len(examples) == 2
