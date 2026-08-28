"""Storage backend interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from infercache.storage.models import CacheEntry


class StorageBackend(ABC):
    @abstractmethod
    def get(self, key: str) -> CacheEntry | None:
        raise NotImplementedError

    @abstractmethod
    def set(self, entry: CacheEntry) -> None:
        raise NotImplementedError

    @abstractmethod
    def delete(self, key: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_entries(self) -> list[CacheEntry]:
        raise NotImplementedError

    @abstractmethod
    def clear(self) -> None:
        raise NotImplementedError

    def count(self) -> int:
        """Entry count. Backends override when they can do better than a full scan."""
        return len(self.list_entries())
