"""Redis-backed cache storage."""

from __future__ import annotations

import json
from dataclasses import asdict

from infercache.storage.base import StorageBackend
from infercache.storage.models import CacheEntry


class RedisStorage(StorageBackend):
    def __init__(self, redis_url: str, prefix: str = "infercache:", ttl_seconds: int | None = None):
        try:
            import redis
        except ImportError as exc:
            raise ImportError("Install infercache[redis] to use Redis backend") from exc
        self._client = redis.from_url(redis_url)
        self._prefix = prefix
        self.ttl_seconds = ttl_seconds

    def _key(self, key: str) -> str:
        return f"{self._prefix}{key}"

    def get(self, key: str) -> CacheEntry | None:
        raw = self._client.get(self._key(key))
        if raw is None:
            return None
        return CacheEntry(**json.loads(raw))

    def set(self, entry: CacheEntry) -> None:
        payload = json.dumps(asdict(entry))
        if self.ttl_seconds:
            self._client.setex(self._key(entry.key), self.ttl_seconds, payload)
        else:
            self._client.set(self._key(entry.key), payload)

    def delete(self, key: str) -> None:
        self._client.delete(self._key(key))

    def list_entries(self) -> list[CacheEntry]:
        keys = self._client.keys(f"{self._prefix}*")
        entries = []
        for k in keys:
            raw = self._client.get(k)
            if raw:
                entries.append(CacheEntry(**json.loads(raw)))
        return entries

    def clear(self) -> None:
        keys = self._client.keys(f"{self._prefix}*")
        if keys:
            self._client.delete(*keys)
