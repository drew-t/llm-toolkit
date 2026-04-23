"""Tests for the QLoRA training harness (config only — no GPU required)."""

from __future__ import annotations

from pathlib import Path

from llm_toolkit.train.qlora import QLoRAConfig


def test_qlora_config_defaults():
    cfg = QLoRAConfig(
        train_data=Path("/tmp/train.jsonl"),
        format_fn=lambda ex: ex["text"],
        output_dir=Path("/tmp/output"),
    )
    assert cfg.base_model == "unsloth/Qwen3-0.6B"
    assert cfg.epochs == 1
    assert cfg.lr == 2e-4
    assert cfg.lora_r == 16
    assert cfg.lora_alpha == 32
    assert cfg.max_seq_len == 512
    assert cfg.batch_size == 8
    assert cfg.gguf_quant == "q4_k_m"


def test_qlora_config_custom():
    cfg = QLoRAConfig(
        base_model="unsloth/Llama-3.2-1B",
        train_data=Path("/tmp/train.jsonl"),
        format_fn=lambda ex: ex["text"],
        output_dir=Path("/tmp/output"),
        epochs=2,
        lr=1e-4,
        lora_r=32,
    )
    assert cfg.base_model == "unsloth/Llama-3.2-1B"
    assert cfg.epochs == 2
    assert cfg.lora_r == 32
