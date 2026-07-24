"""Optional local sentence-transformer embeddings (runs fully on-device)."""

from __future__ import annotations

from infercache.embeddings.base import EmbeddingBackend


class SentenceEmbedding(EmbeddingBackend):
    """
    Local MiniLM (or any sentence-transformers model).

    Requires: pip install "infercache[semantic]"
    First run downloads the model into the user's HF cache (local after that).
    """

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise ImportError(
                'Install semantic extras: pip install "infercache[semantic]"'
            ) from exc
        self.model_name = model_name
        self._model = SentenceTransformer(model_name)

    def embed(self, text: str) -> list[float]:
        vec = self._model.encode(text or "", normalize_embeddings=True)
        return [float(x) for x in vec.tolist()]

    def text_similarity(self, text_a: str, text_b: str) -> float:
        # Prefer pure embedding cosine for neural embeddings
        return self.similarity(self.embed(text_a), self.embed(text_b))
