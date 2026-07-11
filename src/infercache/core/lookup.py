"""Exact and semantic cache lookup."""

from __future__ import annotations

from infercache.config import CacheConfig
from infercache.core.adaptive import AdaptiveThreshold
from infercache.core.keys import make_exact_key
from infercache.embeddings import EmbeddingBackend
from infercache.metrics import CacheMetrics
from infercache.optimization import PromptOptimizer
from infercache.optimization.tokens import estimate_tokens
from infercache.storage import CacheEntry, StorageBackend


class CacheLookup:
    """Handles exact and semantic cache lookups."""

    def __init__(
        self,
        config: CacheConfig,
        storage: StorageBackend,
        embedding: EmbeddingBackend,
        optimizer: PromptOptimizer,
        metrics: CacheMetrics,
        adaptive: AdaptiveThreshold,
    ) -> None:
        self.config = config
        self.storage = storage
        self.embedding = embedding
        self.optimizer = optimizer
        self.metrics = metrics
        self.adaptive = adaptive

    def exact_lookup(self, prompt: str, model: str = "", **kwargs) -> CacheEntry | None:
        if not self.config.enable_exact_cache:
            return None
        key = make_exact_key(prompt, model=model, **kwargs)
        return self.storage.get(key)

    def semantic_lookup(self, prompt: str, model: str = "") -> CacheEntry | None:
        query_emb = self.embedding.embed(prompt)
        threshold = self.config.similarity_threshold
        if self.config.adaptive_threshold:
            threshold = self.adaptive.get_threshold(query_emb)

        # Stage 1: cheap embedding-cosine prefilter to select top-k candidates
        # (ANN-style two-stage retrieval; see GPT Semantic Cache, GPTCache)
        candidates: list[tuple[float, CacheEntry]] = []
        for entry in self.storage.list_entries():
            if not entry.embedding:
                continue
            if entry.metadata and entry.metadata.get("model") and entry.metadata["model"] != model:
                continue
            coarse = self.embedding.similarity(query_emb, entry.embedding)
            candidates.append((coarse, entry))

        candidates.sort(key=lambda x: x[0], reverse=True)
        top_k = max(1, self.config.semantic_top_k)

        # Stage 2: full text similarity on top-k candidates only
        best_entry: CacheEntry | None = None
        best_score = 0.0
        for _, entry in candidates[:top_k]:
            score = self.embedding.text_similarity(prompt, entry.prompt)
            entry_threshold = entry.adaptive_threshold or threshold
            if score >= entry_threshold and score > best_score:
                if score < self.config.min_similarity_for_hit:
                    continue
                best_score = score
                best_entry = entry

        if best_entry:
            best_entry.hits += 1
            self.storage.set(best_entry)
        return best_entry

    def lookup(
        self,
        prompt: str,
        model: str = "",
        optimize: bool = True,
        **kwargs,
    ) -> dict:
        optimized_prompt = prompt
        if optimize:
            optimized_prompt, before, after = self.optimizer.optimize_prompt(prompt)
            self.metrics.record_optimization(before, after)

        entry = self.exact_lookup(optimized_prompt, model=model, **kwargs)
        if entry:
            tokens = estimate_tokens(prompt) + estimate_tokens(entry.response)
            self.metrics.record_hit("exact", tokens)
            return {
                "response": entry.response,
                "cache_hit": True,
                "cache_type": "exact",
                "optimized_prompt": optimized_prompt,
            }

        semantic = self.semantic_lookup(optimized_prompt, model=model)
        if semantic:
            tokens = estimate_tokens(prompt) + estimate_tokens(semantic.response)
            self.metrics.record_hit("semantic", tokens)
            return {
                "response": semantic.response,
                "cache_hit": True,
                "cache_type": "semantic",
                "similarity": True,
                "optimized_prompt": optimized_prompt,
            }

        return {
            "cache_hit": False,
            "optimized_prompt": optimized_prompt,
        }
