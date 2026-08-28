"""Persist CacheMetrics counters alongside SQLite cache data."""

from __future__ import annotations

import sqlite3
import threading
from typing import Any

from infercache.metrics.collector import CacheMetrics
from infercache.storage.sqlite import tune_connection

_SCHEMA = """
CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    total_requests INTEGER DEFAULT 0,
    exact_hits INTEGER DEFAULT 0,
    semantic_hits INTEGER DEFAULT 0,
    misses INTEGER DEFAULT 0,
    tokens_saved INTEGER DEFAULT 0,
    tokens_sent INTEGER DEFAULT 0,
    tokens_before_optimization INTEGER DEFAULT 0,
    tokens_after_optimization INTEGER DEFAULT 0,
    compression_savings INTEGER DEFAULT 0,
    false_positive_avoided INTEGER DEFAULT 0
);
INSERT OR IGNORE INTO metrics (id) VALUES (1);
"""


class PersistentMetrics(CacheMetrics):
    """CacheMetrics that load/save from the same SQLite file as the cache."""

    def __init__(self, path: str) -> None:
        super().__init__()
        self.path = path
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        tune_connection(self._conn)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
        self._load()

    def _load(self) -> None:
        cur = self._conn.execute(
            "SELECT total_requests, exact_hits, semantic_hits, misses, tokens_saved,"
            " tokens_sent, tokens_before_optimization, tokens_after_optimization,"
            " compression_savings, false_positive_avoided FROM metrics WHERE id = 1"
        )
        row = cur.fetchone()
        if not row:
            return
        (
            self.total_requests,
            self.exact_hits,
            self.semantic_hits,
            self.misses,
            self.tokens_saved,
            self.tokens_sent,
            self.tokens_before_optimization,
            self.tokens_after_optimization,
            self.compression_savings,
            self.false_positive_avoided,
        ) = row

    def _save(self) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE metrics SET total_requests=?, exact_hits=?, semantic_hits=?,"
                " misses=?, tokens_saved=?, tokens_sent=?, tokens_before_optimization=?,"
                " tokens_after_optimization=?, compression_savings=?,"
                " false_positive_avoided=? WHERE id=1",
                (
                    self.total_requests,
                    self.exact_hits,
                    self.semantic_hits,
                    self.misses,
                    self.tokens_saved,
                    self.tokens_sent,
                    self.tokens_before_optimization,
                    self.tokens_after_optimization,
                    self.compression_savings,
                    self.false_positive_avoided,
                ),
            )
            self._conn.commit()

    def record_hit(self, kind: str, tokens_saved: int) -> None:
        super().record_hit(kind, tokens_saved)
        self._save()

    def record_miss(self, tokens_sent: int) -> None:
        super().record_miss(tokens_sent)
        self._save()

    def record_optimization(self, before: int, after: int) -> None:
        super().record_optimization(before, after)
        self._save()

    def record_threshold_reject(self) -> None:
        super().record_threshold_reject()
        self._save()

    def reset(self) -> None:
        super().reset()
        self._save()

    def close(self) -> None:
        self._conn.close()
