"""Core cache tests."""

from infercache import CacheConfig, InferCache


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


def test_empty_response_is_not_cached():
    calls = []

    def flaky_llm(prompt: str) -> str:
        calls.append(prompt)
        return "" if len(calls) == 1 else "real answer"

    cache = InferCache(CacheConfig(backend="memory"))
    r1 = cache.get_or_call("question", flaky_llm)
    r2 = cache.get_or_call("question", flaky_llm)
    assert r1["response"] == ""
    assert r2["response"] == "real answer"
    assert len(calls) == 2  # the empty answer was not served from cache


def test_semantic_hit_stays_inside_user_scope():
    config = CacheConfig(
        backend="memory",
        similarity_threshold=0.55,
        semantic_score_margin=0.0,
    )
    cache = InferCache(config=config)
    cache.store("What is the capital of France?", "Paris", model="m", user="alice")

    other_user = cache.lookup("Tell me France's capital city.", model="m", user="bob")
    assert other_user["cache_hit"] is False

    same_user = cache.lookup("Tell me France's capital city.", model="m", user="alice")
    assert same_user["cache_hit"] is True


def test_semantic_lookup_respects_model_scope():
    config = CacheConfig(backend="memory", similarity_threshold=0.55, semantic_score_margin=0.0)
    cache = InferCache(config=config)
    cache.store("What is the capital of France?", "Paris")  # stored with model=""

    wrong_model = cache.lookup("Tell me France's capital city.", model="gpt-4o")
    assert wrong_model["cache_hit"] is False


def test_exact_lookup_includes_confidence():
    cache = InferCache(CacheConfig(backend="memory"))
    cache.store("hello", "world", model="test")
    result = cache.lookup("hello", model="test")
    assert result["confidence"] == 1.0
    assert result["payload_kind"] == "prose"


def test_min_confidence_demotes_semantic_hit():
    config = CacheConfig(
        backend="memory",
        similarity_threshold=0.55,
        semantic_score_margin=0.0,
        min_confidence=1.0,
    )
    cache = InferCache(config=config)
    cache.store("What is the capital of France?", "Paris", model="test")
    result = cache.lookup("Tell me France's capital city.", model="test")
    assert result["cache_hit"] is False
    assert result["confidence"] == 0.0


def test_bypass_forces_fresh_call_but_still_stores():
    calls: list[int] = []

    def llm_fn(prompt: str) -> str:
        calls.append(1)
        return f"answer-{len(calls)}"

    cache = InferCache(CacheConfig(backend="memory"))
    r1 = cache.get_or_call("q", llm_fn)
    r2 = cache.get_or_call("q", llm_fn, bypass=True)
    r3 = cache.get_or_call("q", llm_fn)
    assert r1["cache_hit"] is False
    assert r2["cache_hit"] is False
    assert r3["cache_hit"] is True
    assert r3["response"] == "answer-2"  # bypass refreshed the stored answer
    assert len(calls) == 2


def test_no_store_skips_persistence():
    calls: list[int] = []

    def llm_fn(prompt: str) -> str:
        calls.append(1)
        return "volatile"

    cache = InferCache(CacheConfig(backend="memory"))
    cache.get_or_call("now?", llm_fn, no_store=True)
    r2 = cache.get_or_call("now?", llm_fn, no_store=True)
    assert r2["cache_hit"] is False
    assert len(calls) == 2


def test_sampling_scope_splits_adapter_cache_identity():
    calls: list[float] = []

    def llm_fn(prompt: str) -> str:
        calls.append(1)
        return f"answer-{len(calls)}"

    cache = InferCache(CacheConfig(backend="memory"))
    r1 = cache.get_or_call("same question", llm_fn, temperature=0)
    r2 = cache.get_or_call("same question", llm_fn, temperature=1)
    r3 = cache.get_or_call("same question", llm_fn, temperature=0)
    assert r1["cache_hit"] is False
    assert r2["cache_hit"] is False
    assert r3["cache_hit"] is True
    assert r3["response"] == r1["response"]
    assert len(calls) == 2
