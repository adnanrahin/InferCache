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

try:
    from infercache.embeddings.sentence import SentenceEmbedding

    __all__.append("SentenceEmbedding")
except ImportError:
    pass
