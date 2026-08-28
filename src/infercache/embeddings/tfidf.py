"""TF-IDF embedding backend with optional on-disk corpus statistics."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from collections import Counter
from typing import Sequence

from infercache.embeddings.base import EmbeddingBackend

_TOKEN_RE = re.compile(r"\w+")


class TfidfEmbedding(EmbeddingBackend):
    """
    TF-IDF style embedding.

    When ``state_path`` is set, document frequencies persist to disk so a
    query embedded tomorrow matches vectors stored today. Without it the
    corpus statistics are per-process, and stored embeddings drift after
    every restart.
    """

    def __init__(self, dimensions: int = 512, state_path: str | None = None) -> None:
        self.dimensions = dimensions
        self.state_path = state_path
        self._doc_freq: Counter[str] = Counter()
        self._doc_count = 0
        self._load_state()

    def _tokenize(self, text: str) -> list[str]:
        return _TOKEN_RE.findall(text.lower())

    def _load_state(self) -> None:
        if not self.state_path or not os.path.exists(self.state_path):
            return
        try:
            with open(self.state_path, encoding="utf-8") as f:
                state = json.load(f)
            self._doc_count = int(state.get("doc_count", 0))
            self._doc_freq = Counter(state.get("doc_freq", {}))
        except (OSError, ValueError):
            # A corrupt stats file is not worth failing the cache over
            self._doc_freq = Counter()
            self._doc_count = 0

    def _save_state(self) -> None:
        if not self.state_path:
            return
        tmp = f"{self.state_path}.tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(
                    {"doc_count": self._doc_count, "doc_freq": dict(self._doc_freq)},
                    f,
                    separators=(",", ":"),
                )
            os.replace(tmp, self.state_path)
        except OSError:
            pass

    def update_corpus(self, texts: Sequence[str]) -> None:
        for text in texts:
            tokens = set(self._tokenize(text))
            self._doc_count += 1
            for t in tokens:
                self._doc_freq[t] += 1
        self._save_state()

    def embed(self, text: str) -> list[float]:
        tokens = self._tokenize(text)
        if not tokens:
            return [0.0] * self.dimensions
        tf = Counter(tokens)
        vec = [0.0] * self.dimensions
        n_tokens = len(tokens)
        doc_count = self._doc_count
        doc_freq = self._doc_freq
        for token, count in tf.items():
            h = int(hashlib.blake2b(token.encode(), digest_size=8).hexdigest(), 16)
            idx = h % self.dimensions
            idf = math.log((1 + doc_count) / (1 + doc_freq.get(token, 0))) + 1
            vec[idx] += (count / n_tokens) * idf
        return vec
