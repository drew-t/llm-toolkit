"""Tests for the measurement harness."""

from __future__ import annotations

from llm_toolkit.harness import make_nonce, median_metrics, nonce_prompt


def test_make_nonce_length():
    n = make_nonce()
    assert len(n) == 8
    assert n.isalnum()


def test_make_nonce_unique():
    nonces = {make_nonce() for _ in range(100)}
    assert len(nonces) == 100


def test_nonce_prompt():
    p = nonce_prompt("hello")
    assert p.startswith("[run:")
    assert p.endswith("] hello")
    assert len(p) == len("[run:12345678] hello")


def test_median_metrics_single():
    results = [{"prefill_tok_s": 100.0, "decode_tok_s": 50.0, "wall_time_s": 1.0,
                "prompt_tokens": 10, "gen_tokens": 5}]
    m = median_metrics(results)
    assert m["prefill_tok_s"] == 100.0
    assert m["decode_tok_s"] == 50.0


def test_median_metrics_multiple():
    results = [
        {"prefill_tok_s": 100.0, "decode_tok_s": 50.0, "wall_time_s": 1.0,
         "prompt_tokens": 10, "gen_tokens": 5},
        {"prefill_tok_s": 200.0, "decode_tok_s": 60.0, "wall_time_s": 2.0,
         "prompt_tokens": 10, "gen_tokens": 5},
        {"prefill_tok_s": 150.0, "decode_tok_s": 55.0, "wall_time_s": 1.5,
         "prompt_tokens": 10, "gen_tokens": 5},
    ]
    m = median_metrics(results)
    assert m["prefill_tok_s"] == 150.0
    assert m["decode_tok_s"] == 55.0
    assert m["wall_time_s"] == 1.5


def test_median_metrics_missing_keys():
    results = [{"prefill_tok_s": 100.0}]
    m = median_metrics(results)
    assert m["prefill_tok_s"] == 100.0
    assert m["decode_tok_s"] == 0.0
