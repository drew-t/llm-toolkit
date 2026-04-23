"""GraphWalks context scaling benchmark suite."""

from __future__ import annotations

import hashlib
import json
import random
import re
from pathlib import Path

from llm_toolkit.bench.suite import Suite, TestCase

FIXTURES_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent / "fixtures" / "graphwalks.json"
)
TIERS = [200, 500, 1000, 2000, 4000, 8000, 16000, 32000]
SEED = 42

FOUR_SHOT_PREAMBLE = """\
Example 1:
Edge list: a1b2c3d4e5 -> f6g7h8i9j0
Query: Find all nodes with direct edges to f6g7h8i9j0
Final Answer: [a1b2c3d4e5]

Example 2:
Edge list: x1y2z3a4b5 -> c6d7e8f9g0, h1i2j3k4l5 -> c6d7e8f9g0
Query: Find all nodes with direct edges to c6d7e8f9g0
Final Answer: [x1y2z3a4b5, h1i2j3k4l5]

Example 3:
Edge list: m1n2o3p4q5 -> r6s7t8u9v0, w1x2y3z4a5 -> r6s7t8u9v0, b1c2d3e4f5 -> r6s7t8u9v0
Query: Find all nodes with direct edges to r6s7t8u9v0
Final Answer: [m1n2o3p4q5, w1x2y3z4a5, b1c2d3e4f5]

Example 4:
Edge list: g1h2i3j4k5 -> l6m7n8o9p0, q1r2s3t4u5 -> v6w7x8y9z0
Query: Find all nodes with direct edges to l6m7n8o9p0
Final Answer: [g1h2i3j4k5]
"""


def f1_score(predicted: set[str], truth: set[str]) -> float:
    if not truth and not predicted:
        return 1.0
    if not truth or not predicted:
        return 0.0
    correct = predicted & truth
    precision = len(correct) / len(predicted)
    recall = len(correct) / len(truth)
    denom = precision + recall
    if denom == 0:
        return 0.0
    return round(2 * precision * recall / denom, 4)


def extract_answer_nodes(text: str) -> set[str]:
    match = re.search(r"Final Answer:\s*\[([^\]]*)\]", text, re.IGNORECASE)
    if not match:
        return set()
    raw = match.group(1)
    return {n.strip().strip("'\"") for n in raw.split(",") if n.strip()}


def _make_node_id(rng: random.Random) -> str:
    return hashlib.md5(rng.randbytes(16)).hexdigest()[:10]


def _count_tokens_approx(text: str) -> int:
    return int(len(text.split()) * 1.3)


def generate_fixture(target_tokens: int, rng: random.Random) -> dict:
    num_parents = rng.randint(2, 5)
    target_node = _make_node_id(rng)
    parent_nodes = [_make_node_id(rng) for _ in range(num_parents)]
    edges: list[tuple[str, str]] = [(p, target_node) for p in parent_nodes]
    query_section = (
        f"\n\nFind all nodes with direct edges to node {target_node}.\n\n"
        "Respond with: Final Answer: [node1, node2, ...]"
    )
    header = "Given the following directed graph:\n\nEdge list:\n"
    distractor_pool_size = max(20, target_tokens // 10)
    distractor_nodes = [_make_node_id(rng) for _ in range(distractor_pool_size)]
    distractor_edges: list[tuple[str, str]] = []
    while True:
        src = rng.choice(distractor_nodes)
        dst = rng.choice(distractor_nodes)
        if dst == target_node or src == dst:
            continue
        distractor_edges.append((src, dst))
        check_interval = max(1, min(50, target_tokens // 20))
        if len(distractor_edges) % check_interval == 0:
            all_edges = edges + distractor_edges
            edge_lines = "\n".join(f"{s} -> {d}" for s, d in all_edges)
            full_prompt = FOUR_SHOT_PREAMBLE + header + edge_lines + query_section
            if _count_tokens_approx(full_prompt) >= target_tokens:
                break
    all_edges_merged = list(distractor_edges)
    for parent_edge in edges:
        pos = rng.randint(0, len(all_edges_merged))
        all_edges_merged.insert(pos, parent_edge)
    edge_lines = "\n".join(f"{s} -> {d}" for s, d in all_edges_merged)
    full_prompt = FOUR_SHOT_PREAMBLE + header + edge_lines + query_section
    while _count_tokens_approx(full_prompt) > target_tokens * 1.05 and len(all_edges_merged) > len(
        edges
    ):
        last = all_edges_merged[-1]
        if last[1] == target_node and last[0] in parent_nodes:
            break
        all_edges_merged.pop()
        edge_lines = "\n".join(f"{s} -> {d}" for s, d in all_edges_merged)
        full_prompt = FOUR_SHOT_PREAMBLE + header + edge_lines + query_section
    return {
        "key": f"graphwalks_{target_tokens}",
        "target_tokens": target_tokens,
        "prompt": full_prompt,
        "answer_nodes": sorted(parent_nodes),
    }


def _load_fixtures() -> list[dict]:
    if FIXTURES_PATH.exists():
        with open(FIXTURES_PATH) as f:
            return json.load(f)
    rng = random.Random(SEED)
    return [generate_fixture(tier, rng) for tier in TIERS]


def _graphwalks_scorer(text: str, expected: str) -> float:
    truth = set(expected.split(","))
    predicted = extract_answer_nodes(text)
    return f1_score(predicted, truth)


def context_scaling_suite(tiers: list[int] | None = None) -> Suite:
    fixtures = _load_fixtures()
    if tiers:
        fixtures = [fx for fx in fixtures if fx["target_tokens"] in tiers]
    cases = []
    for fx in fixtures:
        cases.append(
            TestCase(
                key=fx["key"],
                prompt=fx["prompt"],
                expected=",".join(fx["answer_nodes"]),
                score_fn=_graphwalks_scorer,
                metadata={"answer_nodes": fx["answer_nodes"], "tier": fx["target_tokens"]},
            )
        )
    return Suite(
        name="context_scaling",
        cases=cases,
        provider_opts={"max_tokens": 512, "timeout": 1200.0},
    )
