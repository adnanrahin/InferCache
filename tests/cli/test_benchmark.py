"""Benchmark suite tests (seeded, deterministic)."""

from infercache import CacheConfig, InferCache
from infercache.benchmark import run_cache_benchmark, synthetic_workload, to_markdown


def test_benchmark_savings_target():
    cache = InferCache(CacheConfig(similarity_threshold=0.55))
    prompts = synthetic_workload(n=100, repeat_rate=0.5, seed=42)
    result = run_cache_benchmark(cache, prompts, model="gpt-4o-mini").to_dict()

    assert result["total_requests"] == 100
    assert result["hit_rate"] >= 0.20
    assert result["cost"]["reduction_pct"] >= 20


def test_benchmark_report_markdown():
    cache = InferCache()
    prompts = synthetic_workload(n=30, repeat_rate=0.4, seed=7)
    result = run_cache_benchmark(cache, prompts).to_dict()
    md = to_markdown(result)
    assert "# InferCache Benchmark Report" in md
    assert "Hit rate" in md


def test_benchmark_tracks_exact_and_semantic():
    cache = InferCache(CacheConfig(similarity_threshold=0.55))
    prompts = synthetic_workload(n=150, repeat_rate=0.6, paraphrase_rate=0.5, seed=1)
    result = run_cache_benchmark(cache, prompts)
    assert result.exact_hits > 0
    assert result.exact_hits + result.semantic_hits + result.misses == 150
