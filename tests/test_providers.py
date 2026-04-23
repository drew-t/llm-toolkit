"""Tests for provider protocol and implementations."""

from __future__ import annotations

import pytest

from llm_toolkit.providers.base import Response
from llm_toolkit.providers.ollama import OllamaProvider
from llm_toolkit.providers.openai import OpenAIProvider


def test_response_dataclass():
    r = Response(text="hello", prefill_tok_s=100.0, decode_tok_s=50.0,
                 prompt_tokens=10, gen_tokens=5, wall_time_s=0.5)
    assert r.text == "hello"
    assert r.prefill_tok_s == 100.0
    assert r.gen_tokens == 5


def test_ollama_provider_init():
    p = OllamaProvider(base_url="http://localhost:11434")
    assert p.base_url == "http://localhost:11434"


def test_ollama_provider_default_url():
    p = OllamaProvider()
    assert p.base_url == "http://localhost:11434"


def test_openai_provider_init():
    p = OpenAIProvider(base_url="http://localhost:8000")
    assert p.base_url == "http://localhost:8000"


def test_ollama_parse_response():
    raw = {
        "message": {"content": "Hello world"},
        "prompt_eval_count": 15,
        "prompt_eval_duration": 150_000_000,
        "eval_count": 10,
        "eval_duration": 200_000_000,
    }
    r = OllamaProvider._parse_response(raw, wall_time=0.5)
    assert r.text == "Hello world"
    assert r.prompt_tokens == 15
    assert r.gen_tokens == 10
    assert r.wall_time_s == 0.5
    assert r.prefill_tok_s == pytest.approx(100.0, rel=0.01)
    assert r.decode_tok_s == pytest.approx(50.0, rel=0.01)


def test_openai_parse_response():
    raw = {
        "choices": [{"message": {"content": "Hello world"}}],
        "usage": {"prompt_tokens": 15, "completion_tokens": 10},
    }
    r = OpenAIProvider._parse_response(raw, wall_time=0.5)
    assert r.text == "Hello world"
    assert r.prompt_tokens == 15
    assert r.gen_tokens == 10
    assert r.wall_time_s == 0.5
    assert r.prefill_tok_s == 0.0
    assert r.decode_tok_s == 0.0


def test_ollama_parse_response_zero_duration():
    raw = {
        "message": {"content": "hi"},
        "prompt_eval_count": 5,
        "prompt_eval_duration": 0,
        "eval_count": 3,
        "eval_duration": 0,
    }
    r = OllamaProvider._parse_response(raw, wall_time=0.1)
    assert r.prefill_tok_s == 0.0
    assert r.decode_tok_s == 0.0
