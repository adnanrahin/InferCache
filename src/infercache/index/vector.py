"""Local vector index for ANN-style semantic retrieval (numpy or pure Python)."""

from __future__ import annotations

import math
from typing import Sequence


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    try:
        import numpy as np

        va = np.asarray(a, dtype=np.float32)
        vb = np.asarray(b, dtype=np.float32)
        na = float(np.linalg.norm(va))
        nb = float(np.linalg.norm(vb))
        if na == 0 or nb == 0:
            return 0.0
        return float(np.dot(va, vb) / (na * nb))
    except ImportError:
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)


class LocalVectorIndex:
    """
    In-memory vector index keyed by cache entry id.

    Uses FAISS when installed (`infercache[semantic]`), otherwise brute-force
    cosine search (local-first, no network).
    """

    def __init__(self) -> None:
        self._ids: list[str] = []
        self._vectors: list[list[float]] = []
        self._faiss = None
        self._dim: int | None = None
        try:
            import faiss  # type: ignore
            import numpy as np

            self._faiss_mod = faiss
            self._np = np
        except ImportError:
            self._faiss_mod = None
            self._np = None

    def __len__(self) -> int:
        return len(self._ids)

    def clear(self) -> None:
        self._ids.clear()
        self._vectors.clear()
        self._faiss = None
        self._dim = None

    def add(self, entry_id: str, vector: Sequence[float]) -> None:
        if entry_id in self._ids:
            idx = self._ids.index(entry_id)
            self._vectors[idx] = list(vector)
            self._rebuild_faiss()
            return
        self._ids.append(entry_id)
        self._vectors.append(list(vector))
        if self._dim is None:
            self._dim = len(vector)
        if self._faiss_mod is not None and self._np is not None:
            self._ensure_faiss(len(vector))
            assert self._faiss is not None
            v = self._np.asarray([vector], dtype=self._np.float32)
            self._faiss_mod.normalize_L2(v)
            self._faiss.add(v)

    def remove(self, entry_id: str) -> None:
        if entry_id not in self._ids:
            return
        idx = self._ids.index(entry_id)
        self._ids.pop(idx)
        self._vectors.pop(idx)
        self._rebuild_faiss()

    def search(self, query: Sequence[float], top_k: int = 32) -> list[tuple[str, float]]:
        if not self._ids:
            return []
        k = min(top_k, len(self._ids))
        if self._faiss is not None and self._np is not None:
            v = self._np.asarray([query], dtype=self._np.float32)
            self._faiss_mod.normalize_L2(v)
            scores, indices = self._faiss.search(v, k)
            out: list[tuple[str, float]] = []
            for score, idx in zip(scores[0], indices[0]):
                if idx < 0:
                    continue
                out.append((self._ids[int(idx)], float(score)))
            return out

        scored = [
            (entry_id, _cosine(query, vec))
            for entry_id, vec in zip(self._ids, self._vectors)
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]

    def _ensure_faiss(self, dim: int) -> None:
        if self._faiss is None:
            self._faiss = self._faiss_mod.IndexFlatIP(dim)
            self._dim = dim

    def _rebuild_faiss(self) -> None:
        if self._faiss_mod is None or self._np is None or not self._vectors:
            self._faiss = None
            return
        dim = len(self._vectors[0])
        self._faiss = self._faiss_mod.IndexFlatIP(dim)
        mat = self._np.asarray(self._vectors, dtype=self._np.float32)
        self._faiss_mod.normalize_L2(mat)
        self._faiss.add(mat)
        self._dim = dim
