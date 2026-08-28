"""Embedding backend factory."""

from __future__ import annotations

import os

from infercache.embeddings.base import EmbeddingBackend
from infercache.embeddings.hash import HashEmbedding
from infercache.embeddings.tfidf import TfidfEmbedding


def create_embedding_backend(name: str, state_dir: str | None = None) -> EmbeddingBackend:
    if name == "hash":
        return HashEmbedding()
    if name == "tfidf":
        state_path = os.path.join(state_dir, "tfidf_state.json") if state_dir else None
        return TfidfEmbedding(state_path=state_path)
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
