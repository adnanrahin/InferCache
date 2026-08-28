"""Main InferCache engine."""

from __future__ import annotations

import json
import os
from typing import Any, Callable

from infercache.config import CacheConfig
from infercache.core.adaptive import AdaptiveThreshold
from infercache.core.lookup import CacheLookup
from infercache.core.store import CacheStore
from infercache.embeddings import EmbeddingBackend, create_embedding_backend
from infercache.index import LocalVectorIndex
from infercache.metrics import CacheMetrics, PersistentMetrics
from infercache.optimization import PromptOptimizer
from infercache.optimization.tokens import estimate_tokens
from infercache.storage import StorageBackend, create_storage


class InferCache:
    """
    Multi-tier LLM cache combining exact match, semantic similarity,
    adaptive thresholds, vector indexing, and prompt optimization.
    """

    def __init__(
        self,
        config: CacheConfig | None = None,
        embedding: EmbeddingBackend | None = None,
        storage: StorageBackend | None = None,
    ) -> None:
        self.config = config or CacheConfig()
        self.config.validate()
        # Persist embedding state next to the sqlite cache so vectors stored
        # today still match queries embedded after a restart
        state_dir = None
        if self.config.backend == "sqlite":
            state_dir = os.path.dirname(self.config.sqlite_path) or "."
        self.embedding = embedding or create_embedding_backend(
            self.config.embedding_model, state_dir
        )
        self.storage = storage or create_storage(self.config)
        self.optimizer = PromptOptimizer(self.config)

        if self.config.backend == "sqlite" and self.config.persist_metrics:
            self.metrics: CacheMetrics = PersistentMetrics(self.config.sqlite_path)
        else:
            self.metrics = CacheMetrics()

        self._adaptive = AdaptiveThreshold(
            self.config.similarity_threshold,
            self.config.error_rate_target,
        )
        self.vector_index: LocalVectorIndex | None = None
        if self.config.use_vector_index:
            self.vector_index = LocalVectorIndex()
            self._rebuild_index()

        self._lookup = CacheLookup(
            self.config,
            self.storage,
            self.embedding,
            self.optimizer,
            self.metrics,
            self._adaptive,
            self.vector_index,
        )
        self._store = CacheStore(
            self.storage,
            self.embedding,
            self.optimizer,
            self._adaptive,
            self.vector_index,
        )

    def _rebuild_index(self) -> None:
        if self.vector_index is None:
            return
        self.vector_index.clear()
        for entry in self.storage.list_entries():
            if entry.embedding:
                self.vector_index.add(entry.key, entry.embedding)

    def lookup(
        self,
        prompt: str,
        model: str = "",
        optimize: bool = True,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return self._lookup.lookup(prompt, model=model, optimize=optimize, **kwargs)

    def store(
        self,
        prompt: str,
        response: str,
        model: str = "",
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        self._store.store(prompt, response, model=model, metadata=metadata, **kwargs)

    def get_or_call(
        self,
        prompt: str,
        llm_fn: Callable[[str], str],
        model: str = "",
        **kwargs: Any,
    ) -> dict[str, Any]:
        result = self.lookup(prompt, model=model, **kwargs)
        if result.get("cache_hit"):
            return result

        optimized = result["optimized_prompt"]
        response = llm_fn(optimized)
        tokens = estimate_tokens(optimized) + estimate_tokens(response)
        self.metrics.record_miss(tokens)
        if response and response.strip():
            self.store(prompt, response, model=model, **kwargs)
        return {
            "response": response,
            "cache_hit": False,
            "optimized_prompt": optimized,
        }

    def lookup_messages(
        self,
        messages: list[dict[str, Any]],
        model: str = "",
    ) -> dict[str, Any]:
        optimized, before, after = self.optimizer.optimize_messages(messages)
        self.metrics.record_optimization(before, after)
        prompt_repr = json.dumps(optimized, sort_keys=True)
        return self.lookup(prompt_repr, model=model, optimize=False)

    def store_messages(
        self,
        messages: list[dict[str, Any]],
        response: str,
        model: str = "",
    ) -> None:
        optimized, _, _ = self.optimizer.optimize_messages(messages)
        prompt_repr = json.dumps(optimized, sort_keys=True)
        self.store(prompt_repr, response, model=model)

    def get_or_call_messages(
        self,
        messages: list[dict[str, Any]],
        llm_fn: Callable[[list[dict[str, Any]]], str],
        model: str = "",
    ) -> dict[str, Any]:
        optimized, before, after = self.optimizer.optimize_messages(messages)
        self.metrics.record_optimization(before, after)

        prompt_repr = json.dumps(optimized, sort_keys=True)
        cached = self.lookup(prompt_repr, model=model, optimize=False)
        if cached.get("cache_hit"):
            cached["optimized_messages"] = optimized
            return cached

        response = llm_fn(optimized)
        tokens = after + estimate_tokens(response)
        self.metrics.record_miss(tokens)
        if response and response.strip():
            self.store(prompt_repr, response, model=model)
        return {
            "response": response,
            "cache_hit": False,
            "optimized_messages": optimized,
        }

    def feedback(self, prompt: str, was_correct: bool) -> None:
        emb = self.embedding.embed(prompt)
        self._adaptive.record_outcome(emb, was_correct)
        if not was_correct:
            self.metrics.record_threshold_reject()

    def clear(self) -> None:
        self.storage.clear()
        if self.vector_index is not None:
            self.vector_index.clear()

    def stats(self) -> dict[str, Any]:
        return {
            **self.metrics.to_dict(),
            "cache_entries": self.storage.count(),
            "vector_index_size": len(self.vector_index) if self.vector_index else 0,
            "embedding_model": self.config.embedding_model,
            "config": {
                "similarity_threshold": self.config.similarity_threshold,
                "adaptive_threshold": self.config.adaptive_threshold,
                "compression_ratio": self.config.compression_ratio,
                "semantic_score_margin": self.config.semantic_score_margin,
            },
        }
