"""TF-IDF embedding backend."""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from typing import Sequence

from infercache.embeddings.base import EmbeddingBackend


class TfidfEmbedding(EmbeddingBackend):
    """TF-IDF style embedding with in-memory corpus statistics."""

    def __init__(self, dimensions: int = 512) -> None:
        self.dimensions = dimensions
        self._doc_freq: Counter[str] = Counter()
        self._doc_count = 0

    def _tokenize(self, text: str) -> list[str]:
        return re.findall(r"\w+", text.lower())

    def update_corpus(self, texts: Sequence[str]) -> None:
        for text in texts:
            tokens = set(self._tokenize(text))
            self._doc_count += 1
            for t in tokens:
                self._doc_freq[t] += 1

    def embed(self, text: str) -> list[float]:
        tokens = self._tokenize(text)
        if not tokens:
            return [0.0] * self.dimensions
        tf = Counter(tokens)
        vec = [0.0] * self.dimensions
        for token, count in tf.items():
            h = int(hashlib.sha256(token.encode()).hexdigest(), 16)
            idx = h % self.dimensions
            idf = math.log((1 + self._doc_count) / (1 + self._doc_freq.get(token, 0))) + 1
            vec[idx] += (count / len(tokens)) * idf
        return vec
