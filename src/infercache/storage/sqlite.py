"""SQLite-backed persistent cache storage (zero dependencies, survives restarts)."""

from __future__ import annotations

import json
import sqlite3
import threading
import time

from infercache.storage.base import StorageBackend
from infercache.storage.models import CacheEntry

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cache_entries (
    key TEXT PRIMARY KEY,
    prompt TEXT NOT NULL,
    response TEXT NOT NULL,
    embedding TEXT,
    created_at REAL NOT NULL,
    hits INTEGER DEFAULT 0,
    metadata TEXT,
    adaptive_threshold REAL
);
CREATE INDEX IF NOT EXISTS idx_created_at ON cache_entries (created_at);
"""


class SqliteStorage(StorageBackend):
    """Durable local cache. Good default for local installs and the gateway."""

    def __init__(
        self,
        path: str = "infercache.db",
        max_entries: int = 100_000,
        ttl_seconds: int | None = None,
    ) -> None:
        self.path = path
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def _row_to_entry(self, row: tuple) -> CacheEntry:
        return CacheEntry(
            key=row[0],
            prompt=row[1],
            response=row[2],
            embedding=json.loads(row[3]) if row[3] else None,
            created_at=row[4],
            hits=row[5],
            metadata=json.loads(row[6]) if row[6] else None,
            adaptive_threshold=row[7],
        )

    def _expired_cutoff(self) -> float | None:
        if self.ttl_seconds is None:
            return None
        return time.time() - self.ttl_seconds

    def get(self, key: str) -> CacheEntry | None:
        with self._lock:
            cur = self._conn.execute(
                "SELECT key, prompt, response, embedding, created_at, hits, metadata,"
                " adaptive_threshold FROM cache_entries WHERE key = ?",
                (key,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            entry = self._row_to_entry(row)
            cutoff = self._expired_cutoff()
            if cutoff is not None and entry.created_at < cutoff:
                self.delete(key)
                return None
            return entry

    def set(self, entry: CacheEntry) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO cache_entries"
                " (key, prompt, response, embedding, created_at, hits, metadata, adaptive_threshold)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    entry.key,
                    entry.prompt,
                    entry.response,
                    json.dumps(entry.embedding) if entry.embedding else None,
                    entry.created_at,
                    entry.hits,
                    json.dumps(entry.metadata) if entry.metadata else None,
                    entry.adaptive_threshold,
                ),
            )
            # Evict oldest beyond capacity
            self._conn.execute(
                "DELETE FROM cache_entries WHERE key IN ("
                " SELECT key FROM cache_entries ORDER BY created_at DESC"
                " LIMIT -1 OFFSET ?)",
                (self.max_entries,),
            )
            self._conn.commit()

    def delete(self, key: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
            self._conn.commit()

    def list_entries(self) -> list[CacheEntry]:
        with self._lock:
            cutoff = self._expired_cutoff()
            if cutoff is not None:
                self._conn.execute("DELETE FROM cache_entries WHERE created_at < ?", (cutoff,))
                self._conn.commit()
            cur = self._conn.execute(
                "SELECT key, prompt, response, embedding, created_at, hits, metadata,"
                " adaptive_threshold FROM cache_entries"
            )
            return [self._row_to_entry(row) for row in cur.fetchall()]

    def clear(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM cache_entries")
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()
