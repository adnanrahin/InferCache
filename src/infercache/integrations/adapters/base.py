"""Base adapter."""

from __future__ import annotations

from typing import Any

from infercache.config import CacheConfig
from infercache.core import InferCache
from infercache.core.scope import sampling_scope


class BaseAdapter:
    def __init__(self, cache: InferCache | None = None, config: CacheConfig | None = None) -> None:
        self.cache = cache or InferCache(config=config)

    def stats(self) -> dict[str, Any]:
        return self.cache.stats()

    @staticmethod
    def cache_scope(kwargs: dict[str, Any]) -> dict[str, Any]:
        """Sampling fields that must scope the cache key (not forwarded as identity)."""
        return sampling_scope(kwargs)
