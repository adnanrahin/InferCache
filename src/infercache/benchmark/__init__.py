"""Benchmarking: measure hit rate, latency, tokens and dollars saved."""

from infercache.benchmark.datasets import load_jsonl, synthetic_workload
from infercache.benchmark.pricing import cost_usd, get_pricing
from infercache.benchmark.runner import BenchmarkResult, run_cache_benchmark
from infercache.benchmark.report import to_markdown

__all__ = [
    "BenchmarkResult",
    "cost_usd",
    "get_pricing",
    "load_jsonl",
    "run_cache_benchmark",
    "synthetic_workload",
    "to_markdown",
]
