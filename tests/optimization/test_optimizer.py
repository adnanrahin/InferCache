"""Optimization package tests."""

from infercache import InferCache, CacheConfig


def test_prompt_compression_reduces_tokens():
    cache = InferCache(CacheConfig(enable_prompt_compression=True, compression_ratio=0.5))
    long_prompt = (
        "Please kindly explain in order to understand how HTTP caching basically works. "
        "It is very important to understand this. "
        "Could you describe the key mechanisms?"
    )
    _, before, after = cache.optimizer.optimize_prompt(long_prompt)
    assert after <= before


def test_history_pruning():
    cache = InferCache(CacheConfig(max_history_messages=3))
    messages = [{"role": "user", "content": f"msg {i}"} for i in range(10)]
    optimized, _, _ = cache.optimizer.optimize_messages(messages)
    assert len(optimized) <= 3
