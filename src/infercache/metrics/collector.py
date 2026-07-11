"""Cache performance and token savings metrics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class CacheMetrics:
    """Tracks token savings and cache effectiveness."""

    total_requests: int = 0
    exact_hits: int = 0
    semantic_hits: int = 0
    misses: int = 0
    tokens_saved: int = 0
    tokens_sent: int = 0
    tokens_before_optimization: int = 0
    tokens_after_optimization: int = 0
    compression_savings: int = 0
    false_positive_avoided: int = 0

    @property
    def cache_hits(self) -> int:
        return self.exact_hits + self.semantic_hits

    @property
    def hit_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.cache_hits / self.total_requests

    @property
    def token_reduction_pct(self) -> float:
        baseline = self.tokens_before_optimization + self.tokens_saved
        if baseline == 0:
            return 0.0
        saved = self.tokens_saved + self.compression_savings
        return min(100.0, (saved / baseline) * 100)

    @property
    def estimated_cost_reduction_pct(self) -> float:
        if self.total_requests == 0:
            return 0.0
        hit_savings = self.cache_hits / self.total_requests
        opt_savings = 0.0
        if self.tokens_before_optimization > 0:
            opt_savings = self.compression_savings / self.tokens_before_optimization
        return min(100.0, (hit_savings + opt_savings) * 100)

    def record_hit(self, kind: str, tokens_saved: int) -> None:
        self.total_requests += 1
        if kind == "exact":
            self.exact_hits += 1
        else:
            self.semantic_hits += 1
        self.tokens_saved += tokens_saved

    def record_miss(self, tokens_sent: int) -> None:
        self.total_requests += 1
        self.misses += 1
        self.tokens_sent += tokens_sent

    def record_optimization(self, before: int, after: int) -> None:
        self.tokens_before_optimization += before
        self.tokens_after_optimization += after
        if before > after:
            self.compression_savings += before - after

    def record_threshold_reject(self) -> None:
        self.false_positive_avoided += 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_requests": self.total_requests,
            "exact_hits": self.exact_hits,
            "semantic_hits": self.semantic_hits,
            "misses": self.misses,
            "hit_rate": round(self.hit_rate, 4),
            "tokens_saved": self.tokens_saved,
            "compression_savings": self.compression_savings,
            "token_reduction_pct": round(self.token_reduction_pct, 2),
            "estimated_cost_reduction_pct": round(self.estimated_cost_reduction_pct, 2),
            "false_positive_avoided": self.false_positive_avoided,
        }

    def reset(self) -> None:
        for field in self.__dataclass_fields__:
            setattr(self, field, 0)
