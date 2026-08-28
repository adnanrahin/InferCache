"""In-memory LRU cache storage."""

from __future__ import annotations

import time
from collections import OrderedDict

from infercache.storage.base import StorageBackend
from infercache.storage.models import CacheEntry


class MemoryStorage(StorageBackend):
    def __init__(self, max_entries: int = 10_000, ttl_seconds: int | None = None) -> None:
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        self._store: OrderedDict[str, CacheEntry] = OrderedDict()

    def _is_expired(self, entry: CacheEntry) -> bool:
        if self.ttl_seconds is None:
            return False
        return (time.time() - entry.created_at) > self.ttl_seconds

    def get(self, key: str) -> CacheEntry | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        if self._is_expired(entry):
            del self._store[key]
            return None
        self._store.move_to_end(key)
        return entry

    def set(self, entry: CacheEntry) -> None:
        if entry.key in self._store:
            del self._store[entry.key]
        self._store[entry.key] = entry
        while len(self._store) > self.max_entries:
            self._store.popitem(last=False)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def list_entries(self) -> list[CacheEntry]:
        now = time.time()
        expired = [
            key
            for key, entry in self._store.items()
            if self.ttl_seconds and (now - entry.created_at) > self.ttl_seconds
        ]
        for key in expired:
            del self._store[key]
        return list(self._store.values())

    def clear(self) -> None:
        self._store.clear()

    def count(self) -> int:
        return len(self._store)
