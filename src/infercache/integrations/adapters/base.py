"""Base adapter."""

from __future__ import annotations

from typing import Any

from infercache.config import CacheConfig
from infercache.core import InferCache


class BaseAdapter:
    def __init__(self, cache: InferCache | None = None, config: CacheConfig | None = None) -> None:
        self.cache = cache or InferCache(config=config)

    def stats(self) -> dict[str, Any]:
        return self.cache.stats()
