"""JSONL result storage with query/filter and summary tables."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class BenchResult:
    """A single benchmark result entry."""

    benchmark: str
    model: str
    timestamp: float
    metrics: dict
    metadata: dict


class ResultStore:
    """Append-only JSONL result store with query support."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def append(self, result: BenchResult) -> None:
        """Append a result to the store."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as f:
            f.write(json.dumps(asdict(result)) + "\n")

    def _load(self) -> list[BenchResult]:
        """Load all results from the JSONL file."""
        if not self.path.exists():
            return []
        results = []
        for line in self.path.read_text().splitlines():
            line = line.strip()
            if line:
                d = json.loads(line)
                results.append(BenchResult(**d))
        return results

    def query(
        self,
        *,
        benchmark: str | None = None,
        model: str | None = None,
        since: float | None = None,
    ) -> list[BenchResult]:
        """Query results with optional filters."""
        results = self._load()
        if benchmark is not None:
            results = [r for r in results if r.benchmark == benchmark]
        if model is not None:
            results = [r for r in results if r.model == model]
        if since is not None:
            results = [r for r in results if r.timestamp >= since]
        return results

    def summary_table(
        self,
        results: list[BenchResult],
        pivot: str = "model",
        metric: str = "wall_time_s",
    ) -> str:
        """Render a summary table from results."""
        if not results:
            return "(no results)"

        groups: dict[str, list[BenchResult]] = {}
        for r in results:
            key = getattr(r, pivot, "unknown")
            groups.setdefault(key, []).append(r)

        lines = []
        header = f"{'Name':<25} {metric:>12} {'Count':>6}"
        lines.append(header)
        lines.append("-" * len(header))

        for name, group in sorted(groups.items()):
            vals = [r.metrics.get(metric, 0) for r in group]
            avg = sum(vals) / len(vals) if vals else 0
            lines.append(f"{name:<25} {avg:>12.3f} {len(group):>6}")

        return "\n".join(lines)
