"""Invalidation: storage + vector index must stay consistent."""

from infercache import CacheConfig, InferCache


def _cache() -> InferCache:
    return InferCache(CacheConfig(backend="memory", similarity_threshold=0.55, semantic_score_margin=0.0))


def test_invalidate_by_prompt_removes_hit():
    cache = _cache()
    cache.store("What is the capital of France?", "Paris", model="m")
    assert cache.lookup("What is the capital of France?", model="m")["cache_hit"] is True

    removed = cache.invalidate(prompt="What is the capital of France?", model="m")
    assert removed == 1
    assert cache.lookup("What is the capital of France?", model="m")["cache_hit"] is False


def test_invalidate_removes_semantic_neighbor_too():
    cache = _cache()
    cache.store("What is the capital of France?", "Paris", model="m")
    assert cache.lookup("Tell me France's capital city.", model="m")["cache_hit"] is True

    cache.invalidate(prompt="What is the capital of France?", model="m")
    # The embedding is gone from storage and index, so the paraphrase misses.
    assert cache.lookup("Tell me France's capital city.", model="m")["cache_hit"] is False


def test_invalidate_by_tag():
    cache = _cache()
    cache.store("doc question 1", "answer 1", model="m", tags=["docs-v1"])
    cache.store("doc question 2", "answer 2", model="m", tags=["docs-v1"])
    cache.store("unrelated", "keep me", model="m")

    removed = cache.invalidate(tag="docs-v1")
    assert removed == 2
    assert cache.lookup("unrelated", model="m")["cache_hit"] is True
    assert cache.lookup("doc question 1", model="m")["cache_hit"] is False


def test_invalidate_keeps_vector_index_in_sync():
    cache = _cache()
    cache.store("entry one", "1", model="m")
    cache.store("entry two", "2", model="m")
    assert cache.vector_index is not None
    assert len(cache.vector_index) == 2

    cache.invalidate(prompt="entry one", model="m")
    assert len(cache.vector_index) == 1
    assert cache.storage.count() == 1


def test_invalidate_respects_scope_kwargs():
    cache = _cache()
    cache.store("scoped", "a", model="m", user="alice")
    cache.store("scoped", "b", model="m", user="bob")

    removed = cache.invalidate(prompt="scoped", model="m", user="alice")
    assert removed == 1
    assert cache.lookup("scoped", model="m", user="bob")["cache_hit"] is True
    assert cache.lookup("scoped", model="m", user="alice")["cache_hit"] is False


def test_negative_feedback_can_invalidate():
    cache = _cache()
    cache.store("wrong answer prompt", "bad", model="m")
    cache.feedback("wrong answer prompt", was_correct=False, model="m", invalidate=True)
    assert cache.lookup("wrong answer prompt", model="m")["cache_hit"] is False
