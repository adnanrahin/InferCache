"""SQLite storage backend tests."""

import time

from infercache import CacheConfig, InferCache
from infercache.storage import SqliteStorage
from infercache.storage.models import CacheEntry


def _entry(key: str, prompt: str = "p", response: str = "r") -> CacheEntry:
    return CacheEntry(
        key=key, prompt=prompt, response=response,
        embedding=[0.1, 0.2], created_at=time.time(),
    )


def test_sqlite_set_get_delete(tmp_path):
    storage = SqliteStorage(str(tmp_path / "test.db"))
    storage.set(_entry("k1"))
    assert storage.get("k1").response == "r"
    storage.delete("k1")
    assert storage.get("k1") is None
    storage.close()


def test_sqlite_persists_across_instances(tmp_path):
    path = str(tmp_path / "persist.db")
    s1 = SqliteStorage(path)
    s1.set(_entry("k1", prompt="hello", response="world"))
    s1.close()

    s2 = SqliteStorage(path)
    entry = s2.get("k1")
    assert entry is not None
    assert entry.response == "world"
    s2.close()


def test_sqlite_eviction(tmp_path):
    storage = SqliteStorage(str(tmp_path / "evict.db"), max_entries=3)
    for i in range(5):
        e = _entry(f"k{i}")
        e.created_at = time.time() + i  # newer keys later
        storage.set(e)
    entries = storage.list_entries()
    assert len(entries) == 3
    storage.close()


def test_cache_with_sqlite_backend(tmp_path):
    config = CacheConfig(backend="sqlite", sqlite_path=str(tmp_path / "cache.db"))
    cache = InferCache(config=config)
    cache.store("hello", "world", model="test")
    result = cache.lookup("hello", model="test")
    assert result["cache_hit"] is True
    assert result["response"] == "world"


def test_sqlite_count_matches_entries(tmp_path):
    storage = SqliteStorage(str(tmp_path / "count.db"))
    for i in range(4):
        storage.set(_entry(f"k{i}"))
    assert storage.count() == 4
    assert storage.count() == len(storage.list_entries())
    storage.close()


def test_semantic_hit_survives_restart(tmp_path):
    """IDF state persists, so a paraphrase still hits after a new process."""
    db = str(tmp_path / "restart.db")
    config = CacheConfig(
        backend="sqlite",
        sqlite_path=db,
        similarity_threshold=0.55,
        semantic_score_margin=0.0,
    )
    c1 = InferCache(config=config)
    c1.store("What is the capital of France?", "Paris", model="t")

    c2 = InferCache(config=config)  # fresh engine, same files
    hit = c2.lookup("Tell me France's capital city.", model="t")
    assert hit["cache_hit"] is True
    assert hit["response"] == "Paris"
