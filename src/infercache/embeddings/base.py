"""Base embedding interface and text similarity."""

from __future__ import annotations

import math
import re
from abc import ABC, abstractmethod
from difflib import SequenceMatcher
from typing import Sequence

_STOP = frozenset(
    "a an the is are was were be been being have has had do does did will would "
    "could should may might shall can what how why when where who which that this "
    "these those it its of in on at to for with from by as and or not but if me "
    "tell please kindly explain describe".split()
)


class EmbeddingBackend(ABC):
    @abstractmethod
    def embed(self, text: str) -> list[float]:
        raise NotImplementedError

    def similarity(self, a: Sequence[float], b: Sequence[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)

    def _keywords(self, text: str) -> set[str]:
        return {t for t in re.findall(r"\w+", text.lower()) if t not in _STOP and len(t) > 1}

    def _bigrams(self, text: str) -> set[tuple[str, str]]:
        tokens = re.findall(r"\w+", text.lower())
        return {(tokens[i], tokens[i + 1]) for i in range(len(tokens) - 1)}

    def text_similarity(self, text_a: str, text_b: str) -> float:
        emb_score = self.similarity(self.embed(text_a), self.embed(text_b))

        kw_a = self._keywords(text_a)
        kw_b = self._keywords(text_b)
        if kw_a and kw_b:
            keyword_overlap = len(kw_a & kw_b) / len(kw_a | kw_b)
            smaller, larger = (kw_a, kw_b) if len(kw_a) <= len(kw_b) else (kw_b, kw_a)
            concept_coverage = len(smaller & larger) / len(smaller)
        else:
            keyword_overlap = 0.0
            concept_coverage = 0.0

        bg_a = self._bigrams(text_a)
        bg_b = self._bigrams(text_b)
        bigram_overlap = len(bg_a & bg_b) / len(bg_a | bg_b) if bg_a and bg_b else 0.0
        seq_score = SequenceMatcher(None, text_a.lower(), text_b.lower()).ratio()

        return (
            0.15 * emb_score
            + 0.30 * keyword_overlap
            + 0.35 * concept_coverage
            + 0.10 * bigram_overlap
            + 0.10 * seq_score
        )
