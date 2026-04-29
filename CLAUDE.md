# CLAUDE.md

## Commands

```bash
# Install/sync dependencies
uv sync --extra dev

# Tests
uv run pytest              # all tests
uv run pytest -v           # verbose
uv run pytest -k "name"    # by name

# Lint
uv run ruff check src/ tests/
uv run ruff check --fix src/ tests/
uv run ruff format src/ tests/

# Run benchmarks
uv run llm-toolkit bench --suite context_scaling --models qwen3.5:9b
uv run llm-toolkit bench --suite throughput --models qwen3.5:9b
```

## Architecture

Python package for local LLM benchmarking, optimization, and training.

### Core abstractions

- **Provider** (`providers/base.py`): Protocol for LLM backends (Ollama, OpenAI-compatible). Returns `Response` with text + metrics.
- **Suite/TestCase** (`bench/suite.py`): Benchmark definitions. A `Suite` has test cases with prompts, expected outputs, and scoring functions.
- **ResultStore** (`results.py`): JSONL storage with query/filter and summary table rendering.
- **Harness** (`harness.py`): Warm/isolated runs with nonce cache-busting and median aggregation.

### Built-in benchmark suites

- `context_scaling` — GraphWalks directed graph reasoning at 8 token tiers
- `classifier` — Classification accuracy evaluation with per-category breakdown
- `throughput` — Raw prefill/decode speed measurement
- `coding` — Coding task framework with pluggable executors

### Other modules

- `optimize/prompt.py` — Mutation/eval prompt optimization loop
- `train/qlora.py` — Generalized Unsloth QLoRA pipeline
- `train/experiment.py` — Custom training loop harness

## Conventions

- Python 3.12+, managed with uv
- Ruff for linting
- All provider-specific logic behind the Provider protocol
- Suites are functions or classes that produce `Suite` objects

## Web UI (Phase 2)

```bash
# One-time install
cd web && npm install

# Dev (two terminals)
uv run llm-toolkit ui --port 7860     # API server
cd web && npm run dev                 # Vite dev server on :5173 with /api + /ws proxy

# Production-ish: build the SPA, then ui serves it from /
cd web && npm run build
uv run llm-toolkit ui --port 7860     # now also serves the SPA at http://127.0.0.1:7860/

# Tests
cd web && npm test
```
