"""Main InferCache engine."""

from __future__ import annotations

import json
from typing import Any, Callable

from infercache.config import CacheConfig
from infercache.core.adaptive import AdaptiveThreshold
from infercache.core.lookup import CacheLookup
from infercache.core.store import CacheStore
from infercache.embeddings import EmbeddingBackend, create_embedding_backend
from infercache.metrics import CacheMetrics
from infercache.optimization import PromptOptimizer
from infercache.optimization.tokens import estimate_tokens
from infercache.storage import StorageBackend, create_storage


class InferCache:
    """
    Multi-tier LLM cache combining exact match, semantic similarity,
    adaptive thresholds, and prompt optimization.
    """

    def __init__(
        self,
        config: CacheConfig | None = None,
        embedding: EmbeddingBackend | None = None,
        storage: StorageBackend | None = None,
    ) -> None:
        self.config = config or CacheConfig()
        self.config.validate()
        self.embedding = embedding or create_embedding_backend(self.config.embedding_model)
        self.storage = storage or create_storage(self.config)
        self.optimizer = PromptOptimizer(self.config)
        self.metrics = CacheMetrics()
        self._adaptive = AdaptiveThreshold(
            self.config.similarity_threshold,
            self.config.error_rate_target,
        )
        self._lookup = CacheLookup(
            self.config,
            self.storage,
            self.embedding,
            self.optimizer,
            self.metrics,
            self._adaptive,
        )
        self._store = CacheStore(self.storage, self.embedding, self.optimizer, self._adaptive)

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

    def stats(self) -> dict[str, Any]:
        return {
            **self.metrics.to_dict(),
            "cache_entries": len(self.storage.list_entries()),
            "config": {
                "similarity_threshold": self.config.similarity_threshold,
                "adaptive_threshold": self.config.adaptive_threshold,
                "compression_ratio": self.config.compression_ratio,
            },
        }
