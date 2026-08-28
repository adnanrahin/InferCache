"""Cache write operations."""

from __future__ import annotations

import time
from typing import Any

from infercache.core.adaptive import AdaptiveThreshold
from infercache.core.keys import make_exact_key
from infercache.embeddings import EmbeddingBackend
from infercache.index import LocalVectorIndex
from infercache.optimization import PromptOptimizer
from infercache.storage import CacheEntry, StorageBackend


class CacheStore:
    """Handles cache entry persistence."""

    def __init__(
        self,
        storage: StorageBackend,
        embedding: EmbeddingBackend,
        optimizer: PromptOptimizer,
        adaptive: AdaptiveThreshold,
        vector_index: LocalVectorIndex | None = None,
    ) -> None:
        self.storage = storage
        self.embedding = embedding
        self.optimizer = optimizer
        self.adaptive = adaptive
        self.vector_index = vector_index

    def store(
        self,
        prompt: str,
        response: str,
        model: str = "",
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> CacheEntry:
        optimized_prompt, _, _ = self.optimizer.optimize_prompt(prompt)
        key = make_exact_key(optimized_prompt, model=model, **kwargs)
        emb = self.embedding.embed(optimized_prompt)
        # kwargs scope the exact key, so they must scope semantic matches too
        meta = {"model": model, **kwargs, **(metadata or {})}
        entry = CacheEntry(
            key=key,
            prompt=optimized_prompt,
            response=response,
            embedding=emb,
            created_at=time.time(),
            metadata=meta,
            adaptive_threshold=self.adaptive.get_threshold(emb),
        )
        self.storage.set(entry)
        if self.vector_index is not None and emb:
            self.vector_index.add(key, emb)
        if hasattr(self.embedding, "update_corpus"):
            self.embedding.update_corpus([optimized_prompt])
        return entry
