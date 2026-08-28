"""Configuration for InferCache."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from infercache.config.paths import default_cache_path


@dataclass
class CacheConfig:
    """Settings controlling cache behavior and token optimization.

    Local-first: every backend runs on the user's machine. "sqlite" persists
    to ~/.infercache/cache.db and is the default everywhere, "memory" is
    per-process, "redis" is optional for teams that already run one — never
    required.
    """

    similarity_threshold: float = 0.80
    adaptive_threshold: bool = True
    max_cache_entries: int = 10_000
    # A cache that forgets within the hour never pays for itself.
    ttl_seconds: int | None = 7 * 24 * 3600

    enable_exact_cache: bool = True

    # Off by default: dropping sentences changes meaning and breaks
    # provider-side prefix caching. Opt in per app if you know your workload.
    enable_prompt_compression: bool = False
    compression_ratio: float = 0.7
    enable_history_pruning: bool = True
    max_history_messages: int = 10
    enable_prefix_optimization: bool = True

    static_prefix_min_tokens: int = 256

    min_similarity_for_hit: float = 0.45
    error_rate_target: float = 0.03
    # Require best semantic score to beat 2nd-best by this margin (safer hits)
    semantic_score_margin: float = 0.02
    # Prefer embedding cosine over lexical blend for neural backends
    prefer_embedding_score: bool = True

    backend: Literal["memory", "redis", "sqlite"] = "sqlite"
    redis_url: str | None = None
    sqlite_path: str = field(default_factory=default_cache_path)
    persist_metrics: bool = True

    # Semantic lookup performance: rank candidates by embedding cosine first,
    # then run full text similarity only on the top-k (GPT Semantic Cache ANN pattern)
    semantic_top_k: int = 32
    use_vector_index: bool = True

    # tfidf | hash | minilm | sentence-transformers/<model>
    embedding_model: str = "tfidf"

    extra: dict = field(default_factory=dict)

    def validate(self) -> None:
        if not 0.0 < self.similarity_threshold <= 1.0:
            raise ValueError("similarity_threshold must be in (0, 1]")
        if not 0.0 < self.compression_ratio <= 1.0:
            raise ValueError("compression_ratio must be in (0, 1]")
        if self.max_cache_entries < 1:
            raise ValueError("max_cache_entries must be >= 1")
        if self.semantic_score_margin < 0:
            raise ValueError("semantic_score_margin must be >= 0")
