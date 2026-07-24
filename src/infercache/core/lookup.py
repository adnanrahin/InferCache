"""Exact and semantic cache lookup with vector index + safer accept rules."""

from __future__ import annotations

from infercache.config import CacheConfig
from infercache.core.adaptive import AdaptiveThreshold
from infercache.core.keys import make_exact_key
from infercache.embeddings import EmbeddingBackend
from infercache.index import LocalVectorIndex
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
        vector_index: LocalVectorIndex | None = None,
    ) -> None:
        self.config = config
        self.storage = storage
        self.embedding = embedding
        self.optimizer = optimizer
        self.metrics = metrics
        self.adaptive = adaptive
        self.vector_index = vector_index

    def exact_lookup(self, prompt: str, model: str = "", **kwargs) -> CacheEntry | None:
        if not self.config.enable_exact_cache:
            return None
        key = make_exact_key(prompt, model=model, **kwargs)
        return self.storage.get(key)

    def _score_pair(self, query: str, query_emb: list[float], entry: CacheEntry) -> float:
        # Weak sparse embeddings are poor paraphrase signals — use lexical/hybrid.
        if self.config.embedding_model in ("tfidf", "hash") or not entry.embedding:
            return self.embedding.text_similarity(query, entry.prompt)
        # Neural backends: trust cosine when prefer_embedding_score is on
        if self.config.prefer_embedding_score:
            return self.embedding.similarity(query_emb, entry.embedding)
        return self.embedding.text_similarity(query, entry.prompt)

    def semantic_lookup(self, prompt: str, model: str = "") -> CacheEntry | None:
        query_emb = self.embedding.embed(prompt)
        threshold = self.config.similarity_threshold
        if self.config.adaptive_threshold:
            threshold = self.adaptive.get_threshold(query_emb)
        threshold = max(threshold, self.config.min_similarity_for_hit)

        # Stage 1: vector index / embedding prefilter
        candidates: list[CacheEntry] = []
        if self.vector_index is not None and len(self.vector_index) > 0:
            for entry_id, _ in self.vector_index.search(query_emb, self.config.semantic_top_k):
                entry = self.storage.get(entry_id)
                if entry is None:
                    continue
                if entry.metadata and entry.metadata.get("model") and entry.metadata["model"] != model:
                    continue
                candidates.append(entry)
        else:
            scored: list[tuple[float, CacheEntry]] = []
            for entry in self.storage.list_entries():
                if not entry.embedding:
                    continue
                if entry.metadata and entry.metadata.get("model") and entry.metadata["model"] != model:
                    continue
                scored.append((self.embedding.similarity(query_emb, entry.embedding), entry))
            scored.sort(key=lambda x: x[0], reverse=True)
            candidates = [e for _, e in scored[: max(1, self.config.semantic_top_k)]]

        # Stage 2: full score + margin check (safer semantic accept)
        ranked: list[tuple[float, CacheEntry]] = []
        for entry in candidates:
            score = self._score_pair(prompt, query_emb, entry)
            ranked.append((score, entry))
        ranked.sort(key=lambda x: x[0], reverse=True)

        if not ranked:
            return None

        best_score, best_entry = ranked[0]
        second = ranked[1][0] if len(ranked) > 1 else 0.0

        if best_score < threshold:
            return None
        if best_score - second < self.config.semantic_score_margin and len(ranked) > 1:
            # Ambiguous between two near neighbors — refuse to avoid wrong hit
            self.metrics.record_threshold_reject()
            return None

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
