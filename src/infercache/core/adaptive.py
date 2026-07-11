"""Adaptive similarity thresholds (VectorQ / vCache inspired)."""

from __future__ import annotations

import hashlib
import json


class AdaptiveThreshold:
    """Per-embedding threshold learning."""

    def __init__(self, base: float = 0.85, error_target: float = 0.03) -> None:
        self.base = base
        self.error_target = error_target
        self._stats: dict[str, dict[str, float]] = {}

    def _bucket(self, embedding: list[float]) -> str:
        if not embedding:
            return "default"
        sample = embedding[:16]
        return hashlib.md5(json.dumps([round(x, 3) for x in sample]).encode()).hexdigest()[:8]

    def get_threshold(self, embedding: list[float]) -> float:
        bucket = self._bucket(embedding)
        stats = self._stats.get(bucket)
        if not stats:
            return self.base
        hits = stats.get("hits", 0)
        errors = stats.get("errors", 0)
        total = hits + errors
        if total < 5:
            return self.base
        error_rate = errors / total
        if error_rate > self.error_target:
            return min(0.99, self.base + 0.05)
        if error_rate < self.error_target / 2:
            return max(0.70, self.base - 0.03)
        return self.base

    def record_outcome(self, embedding: list[float], was_correct: bool) -> None:
        bucket = self._bucket(embedding)
        if bucket not in self._stats:
            self._stats[bucket] = {"hits": 0, "errors": 0}
        key = "hits" if was_correct else "errors"
        self._stats[bucket][key] += 1
