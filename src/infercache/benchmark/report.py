"""Benchmark report formatting."""

from __future__ import annotations

from typing import Any


def to_markdown(result: dict[str, Any]) -> str:
    tokens = result["tokens"]
    cost = result["cost"]
    latency = result["latency_ms"]
    lines = [
        "# InferCache Benchmark Report",
        "",
        f"Model: `{result['model']}` | Requests: {result['total_requests']}"
        f" | Wall time: {result['wall_time_s']}s",
        "",
        "## Cache performance",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Hit rate | {result['hit_rate'] * 100:.1f}% |",
        f"| Exact hits | {result['exact_hits']} |",
        f"| Semantic hits | {result['semantic_hits']} |",
        f"| Misses | {result['misses']} |",
        "",
        "## Token savings",
        "",
        "| Direction | Saved | Spent |",
        "|-----------|-------|-------|",
        f"| Input | {tokens['input_saved']:,} | {tokens['input_spent']:,} |",
        f"| Output | {tokens['output_saved']:,} | {tokens['output_spent']:,} |",
        "",
        "## Cost",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Saved | ${cost['saved_usd']:.4f} |",
        f"| Spent | ${cost['spent_usd']:.4f} |",
        f"| **Reduction** | **{cost['reduction_pct']:.1f}%** |",
        "",
        "## Latency (ms)",
        "",
        "| Path | Avg | P95 |",
        "|------|-----|-----|",
        f"| Cache hit | {latency['hit_avg']} | {latency['hit_p95']} |",
        f"| Cache miss (LLM) | {latency['miss_avg']} | {latency['miss_p95']} |",
        "",
    ]
    return "\n".join(lines)
