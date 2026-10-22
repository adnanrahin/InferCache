"""Adaptive similarity thresholds (VectorQ / vCache inspired)."""

from __future__ import annotations

import hashlib
import json
import os


class AdaptiveThreshold:
    """Per-embedding threshold learning, optionally persisted as a JSON sidecar."""

    def __init__(
        self,
        base: float = 0.85,
        error_target: float = 0.03,
        state_path: str | None = None,
    ) -> None:
        self.base = base
        self.error_target = error_target
        self.state_path = state_path
        self._stats: dict[str, dict[str, float]] = {}
        self._load()

    def _load(self) -> None:
        if not self.state_path or not os.path.exists(self.state_path):
            return
        try:
            with open(self.state_path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            return
        if isinstance(data, dict):
            self._stats = {
                str(bucket): {"hits": float(v.get("hits", 0)), "errors": float(v.get("errors", 0))}
                for bucket, v in data.items()
                if isinstance(v, dict)
            }

    def _save(self) -> None:
        if not self.state_path:
            return
        tmp_path = f"{self.state_path}.tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as fh:
                json.dump(self._stats, fh)
            os.replace(tmp_path, self.state_path)
        except OSError:
            # Persistence is best-effort; in-memory learning still applies.
            pass

    def _bucket(self, embedding: list[float]) -> str:
        if not embedding:
            return "default"
        sample = embedding[:16]
        digest = hashlib.md5(  # usedforsecurity=False: fingerprint only, not auth
            json.dumps([round(x, 3) for x in sample]).encode(),
            usedforsecurity=False,
        )
        return digest.hexdigest()[:8]

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

    def bucket_accuracy(self, embedding: list[float]) -> float:
        """Historical hit fraction for this bucket, or 1.0 when unknown."""
        stats = self._stats.get(self._bucket(embedding))
        if not stats:
            return 1.0
        total = stats.get("hits", 0) + stats.get("errors", 0)
        if total < 5:
            return 1.0
        return stats["hits"] / total

    def record_outcome(self, embedding: list[float], was_correct: bool) -> None:
        bucket = self._bucket(embedding)
        if bucket not in self._stats:
            self._stats[bucket] = {"hits": 0, "errors": 0}
        key = "hits" if was_correct else "errors"
        self._stats[bucket][key] += 1
        self._save()
