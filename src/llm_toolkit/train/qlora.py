"""Generalized QLoRA fine-tuning pipeline.

Wraps Unsloth + TRL for QLoRA training with GGUF export.
Training dependencies are optional — import errors are deferred to runtime.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass
class QLoRAConfig:
    """Configuration for a QLoRA fine-tuning run."""

    train_data: Path
    format_fn: Callable[[dict], str]
    output_dir: Path
    base_model: str = "unsloth/Qwen3-0.6B"
    epochs: int = 1
    lr: float = 2e-4
    lora_r: int = 16
    lora_alpha: int = 32
    max_seq_len: int = 512
    batch_size: int = 8
    gguf_quant: str = "q4_k_m"
    val_data: Path | None = None


@dataclass
class TrainResult:
    """Result of a QLoRA training run."""

    output_dir: Path
    gguf_path: Path | None
    train_loss: float | None = None
    train_samples: int = 0


def load_jsonl(path: Path) -> list[dict]:
    """Load examples from a JSONL file."""
    examples = []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if line:
                examples.append(json.loads(line))
    return examples


def run_qlora(config: QLoRAConfig) -> TrainResult:
    """Run QLoRA fine-tuning and export to GGUF.

    Requires: unsloth, datasets, trl, transformers, torch
    Install with: pip install llm-toolkit[train]
    """
    import unsloth  # noqa: F401
    from datasets import Dataset
    from trl import SFTConfig, SFTTrainer
    from unsloth import FastLanguageModel

    train_raw = load_jsonl(config.train_data)
    train_formatted = [{"text": config.format_fn(ex)} for ex in train_raw]
    train_dataset = Dataset.from_list(train_formatted)

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=config.base_model,
        max_seq_length=config.max_seq_len,
        load_in_4bit=True,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = FastLanguageModel.get_peft_model(
        model,
        r=config.lora_r,
        lora_alpha=config.lora_alpha,
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
        lora_dropout=0,
        bias="none",
        use_gradient_checkpointing="unsloth",
    )

    config.output_dir.mkdir(parents=True, exist_ok=True)

    trainer = SFTTrainer(
        model=model,
        processing_class=tokenizer,
        train_dataset=train_dataset,
        args=SFTConfig(
            output_dir=str(config.output_dir),
            num_train_epochs=config.epochs,
            per_device_train_batch_size=config.batch_size,
            gradient_accumulation_steps=1,
            learning_rate=config.lr,
            lr_scheduler_type="cosine",
            warmup_ratio=0.1,
            logging_steps=10,
            save_strategy="epoch",
            bf16=True,
            seed=42,
            report_to="none",
            dataset_text_field="text",
            max_length=config.max_seq_len,
        ),
    )

    train_output = trainer.train()

    gguf_dir = config.output_dir / "gguf"
    model.save_pretrained_gguf(
        str(gguf_dir),
        tokenizer,
        quantization_method=config.gguf_quant,
    )

    return TrainResult(
        output_dir=config.output_dir,
        gguf_path=gguf_dir,
        train_loss=train_output.training_loss if hasattr(train_output, "training_loss") else None,
        train_samples=len(train_raw),
    )
