"""Vector index + safer semantic + cascade tests."""

from infercache import CacheConfig, CascadeStage, InferCache, ModelCascade
from infercache.index import LocalVectorIndex
from infercache.metrics import PersistentMetrics


def test_vector_index_search():
    idx = LocalVectorIndex()
    idx.add("a", [1.0, 0.0, 0.0])
    idx.add("b", [0.0, 1.0, 0.0])
    idx.add("c", [0.9, 0.1, 0.0])
    hits = idx.search([1.0, 0.0, 0.0], top_k=2)
    assert hits[0][0] == "a"
    assert hits[0][1] > hits[1][1]


def test_persistent_metrics(tmp_path):
    path = str(tmp_path / "m.db")
    m1 = PersistentMetrics(path)
    m1.record_hit("exact", 10)
    m1.record_miss(5)
    m1.close()

    m2 = PersistentMetrics(path)
    assert m2.exact_hits == 1
    assert m2.misses == 1
    assert m2.tokens_saved == 10
    m2.close()


def test_engine_with_vector_index_and_sqlite(tmp_path):
    db = str(tmp_path / "c.db")
    cache = InferCache(
        CacheConfig(
            backend="sqlite",
            sqlite_path=db,
            use_vector_index=True,
            similarity_threshold=0.5,
            semantic_score_margin=0.0,
        )
    )
    cache.store("What is the capital of France?", "Paris", model="t")
    hit = cache.lookup("What is the capital of France?", model="t")
    assert hit["cache_hit"] is True
    assert cache.vector_index is not None
    assert len(cache.vector_index) >= 1


def test_cascade_uses_cheap_then_stops():
    calls = []

    def cheap(p: str) -> str:
        calls.append("cheap")
        return "A detailed enough answer from the small model that should not escalate."

    def expensive(p: str) -> str:
        calls.append("expensive")
        return "Big model answer"

    cache = InferCache(CacheConfig(backend="memory"))
    cascade = ModelCascade(
        cache,
        [
            CascadeStage("small", cheap),
            CascadeStage("big", expensive),
        ],
    )
    result = cascade.complete("Explain caching briefly")
    assert result["model_used"] == "small"
    assert calls == ["cheap"]
    assert result["escalated"] is False


def test_cascade_escalates_on_uncertain():
    calls = []

    def cheap(p: str) -> str:
        calls.append("cheap")
        return "I am not sure."

    def expensive(p: str) -> str:
        calls.append("expensive")
        return "Here is a confident full answer about the topic."

    cache = InferCache(CacheConfig(backend="memory"))
    cascade = ModelCascade(
        cache,
        [
            CascadeStage("small", cheap),
            CascadeStage("big", expensive),
        ],
    )
    result = cascade.complete("Hard question")
    assert result["model_used"] == "big"
    assert calls == ["cheap", "expensive"]
    assert result["escalated"] is True
