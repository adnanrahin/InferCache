"""Optimization package tests."""

from infercache import CacheConfig, InferCache


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


def test_json_prompt_is_not_sentence_dropped():
    cache = InferCache(CacheConfig(enable_prompt_compression=True, compression_ratio=0.1))
    payload = '{"error": "disk full", "retries": 3, "hosts": ["a", "b", "c"]}'
    text, _, _ = cache.optimizer.optimize_prompt(payload)
    assert text == payload


def test_frozen_system_prefix_is_byte_identical():
    prefix = "You are a policy engine. " * 80  # well above static_prefix_min_tokens
    cache = InferCache(CacheConfig(enable_prompt_compression=True, compression_ratio=0.1))
    messages = [
        {"role": "system", "content": prefix},
        {"role": "user", "content": "Please kindly explain caching. It is very important. Could you describe it?"},
    ]
    optimized, _, _ = cache.optimizer.optimize_messages(messages)
    assert optimized[0]["role"] == "system"
    assert optimized[0]["content"] == prefix
