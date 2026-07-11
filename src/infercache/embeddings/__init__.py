"""Embedding backends for semantic similarity."""

from infercache.embeddings.base import EmbeddingBackend
from infercache.embeddings.factory import create_embedding_backend
from infercache.embeddings.hash import HashEmbedding
from infercache.embeddings.tfidf import TfidfEmbedding

__all__ = [
    "EmbeddingBackend",
    "HashEmbedding",
    "TfidfEmbedding",
    "create_embedding_backend",
]
