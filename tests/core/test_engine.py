"""Core cache tests."""

from infercache import InferCache, CacheConfig


def test_exact_cache_hit():
    cache = InferCache()
    cache.store("hello", "world", model="test")
    result = cache.lookup("hello", model="test")
    assert result["cache_hit"] is True
    assert result["cache_type"] == "exact"
    assert result["response"] == "world"


def test_semantic_cache_paraphrase():
    config = CacheConfig(similarity_threshold=0.55)
    cache = InferCache(config=config)
    cache.store("What is the capital of France?", "Paris", model="test")
    result = cache.lookup("Tell me France's capital city.", model="test")
    assert result["cache_hit"] is True
    assert result["response"] == "Paris"


def test_get_or_call_miss_then_hit():
    calls = []

    def llm_fn(prompt: str) -> str:
        calls.append(prompt)
        return "answer"

    cache = InferCache()
    r1 = cache.get_or_call("query", llm_fn)
    r2 = cache.get_or_call("query", llm_fn)
    assert r1["cache_hit"] is False
    assert r2["cache_hit"] is True
    assert len(calls) == 1


def test_metrics_token_reduction():
    cache = InferCache()
    for _ in range(5):
        cache.store("same", "resp")
    for _ in range(5):
        cache.lookup("same")
    stats = cache.stats()
    assert stats["hit_rate"] == 1.0
    assert stats["exact_hits"] == 5
