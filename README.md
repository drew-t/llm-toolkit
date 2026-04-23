# llm-toolkit

General-purpose local LLM benchmarking, prompt optimization, and fine-tuning toolkit.

## Install

```bash
uv add llm-toolkit
```

## Quick start

```bash
# Benchmark context scaling
llm-toolkit bench --suite context_scaling --models qwen3.5:9b --url http://localhost:11434

# Benchmark throughput
llm-toolkit bench --suite throughput --models qwen3.5:9b --url http://localhost:11434
```
