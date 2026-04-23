"""General-purpose experiment training harness."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ExperimentConfig:
    """Configuration for a custom training experiment."""

    name: str
    train_data: Path
    output_dir: Path
    epochs: int = 10
    batch_size: int = 32
    lr: float = 1e-3
    val_data: Path | None = None
    checkpoint_every: int = 1
    log_every: int = 10
    seed: int = 42


@dataclass
class EpochMetrics:
    """Metrics for a single training epoch."""

    epoch: int
    train_loss: float
    val_loss: float | None = None
    val_accuracy: float | None = None
    duration_s: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExperimentResult:
    """Result of a complete training experiment."""

    name: str
    config: ExperimentConfig
    epoch_metrics: list[EpochMetrics] = field(default_factory=list)
    total_duration_s: float = 0.0
    best_epoch: int = 0
    best_val_metric: float = 0.0


def load_jsonl(path: Path) -> list[dict]:
    """Load examples from a JSONL file."""
    examples = []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if line:
                examples.append(json.loads(line))
    return examples


def save_experiment_log(result: ExperimentResult, path: Path) -> None:
    """Save experiment results to JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    log = {
        "name": result.name,
        "total_duration_s": result.total_duration_s,
        "best_epoch": result.best_epoch,
        "best_val_metric": result.best_val_metric,
        "epochs": [
            {
                "epoch": m.epoch,
                "train_loss": m.train_loss,
                "val_loss": m.val_loss,
                "val_accuracy": m.val_accuracy,
                "duration_s": m.duration_s,
                **m.extra,
            }
            for m in result.epoch_metrics
        ],
    }
    path.write_text(json.dumps(log, indent=2))
