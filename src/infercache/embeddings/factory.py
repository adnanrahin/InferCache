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
    raise ValueError(f"Unknown embedding backend: {name}")
