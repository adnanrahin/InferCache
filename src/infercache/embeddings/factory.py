"""Embedding backend factory."""

from __future__ import annotations

from infercache.embeddings.base import EmbeddingBackend
from infercache.embeddings.hash import HashEmbedding
from infercache.embeddings.tfidf import TfidfEmbedding


def create_embedding_backend(name: str) -> EmbeddingBackend:
    if name == "hash":
        return HashEmbedding()
    if name == "tfidf":
        return TfidfEmbedding()
    if name in ("minilm", "sentence", "sentence-transformers"):
        from infercache.embeddings.sentence import SentenceEmbedding

        return SentenceEmbedding()
    if name.startswith("sentence-transformers/") or "/" in name:
        from infercache.embeddings.sentence import SentenceEmbedding

        return SentenceEmbedding(model_name=name)
    raise ValueError(
        f"Unknown embedding backend: {name}. "
        "Use tfidf|hash|minilm or a sentence-transformers model id."
    )
