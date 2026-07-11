"""Storage backend factory."""

from __future__ import annotations

from infercache.config import CacheConfig
from infercache.storage.base import StorageBackend
from infercache.storage.memory import MemoryStorage
from infercache.storage.redis import RedisStorage
from infercache.storage.sqlite import SqliteStorage


def create_storage(config: CacheConfig) -> StorageBackend:
    if config.backend == "redis":
        if not config.redis_url:
            raise ValueError("redis_url required for redis backend")
        return RedisStorage(config.redis_url, ttl_seconds=config.ttl_seconds)
    if config.backend == "sqlite":
        return SqliteStorage(
            config.sqlite_path,
            max_entries=config.max_cache_entries,
            ttl_seconds=config.ttl_seconds,
        )
    return MemoryStorage(config.max_cache_entries, config.ttl_seconds)
