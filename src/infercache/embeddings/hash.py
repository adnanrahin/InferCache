"""Hash-based embedding backend."""

from __future__ import annotations

import hashlib
import re

from infercache.embeddings.base import EmbeddingBackend


class HashEmbedding(EmbeddingBackend):
    """Deterministic hash-based embedding (zero dependencies)."""

    def __init__(self, dimensions: int = 256) -> None:
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        text = text.lower().strip()
        vec = [0.0] * self.dimensions
        for token in re.findall(r"\w+", text):
            h = int(hashlib.md5(token.encode()).hexdigest(), 16)
            idx = h % self.dimensions
            sign = 1.0 if (h >> 8) % 2 == 0 else -1.0
            vec[idx] += sign
        return vec
