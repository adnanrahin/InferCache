"""Local vector index for ANN-style semantic retrieval (FAISS, numpy, or pure Python)."""

from __future__ import annotations

import math
from typing import Sequence

try:
    import numpy as _np
except ImportError:
    _np = None

try:
    import faiss as _faiss  # type: ignore
except ImportError:
    _faiss = None


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class LocalVectorIndex:
    """
    In-memory vector index keyed by cache entry id.

    Search path, best available first: FAISS inner-product index, a single
    normalized numpy matrix product, then brute-force cosine in pure Python.
    All local, no network.

    Vectors whose dimension doesn't match the first one added are ignored —
    they come from a different embedding backend and can't score meaningfully
    against current queries.
    """

    def __init__(self) -> None:
        self._ids: list[str] = []
        self._pos: dict[str, int] = {}
        self._vectors: list[list[float]] = []
        self._dim: int | None = None
        self._matrix = None  # normalized numpy matrix, rebuilt lazily
        self._dirty = False
        self._faiss = None

    def __len__(self) -> int:
        return len(self._ids)

    def clear(self) -> None:
        self._ids.clear()
        self._pos.clear()
        self._vectors.clear()
        self._dim = None
        self._matrix = None
        self._dirty = False
        self._faiss = None

    def add(self, entry_id: str, vector: Sequence[float]) -> None:
        if not vector:
            return
        if self._dim is None:
            self._dim = len(vector)
        elif len(vector) != self._dim:
            return

        idx = self._pos.get(entry_id)
        if idx is not None:
            self._vectors[idx] = list(vector)
            self._invalidate()
            return

        self._pos[entry_id] = len(self._ids)
        self._ids.append(entry_id)
        self._vectors.append(list(vector))

        if _faiss is not None and _np is not None:
            if self._faiss is None:
                self._faiss = _faiss.IndexFlatIP(self._dim)
            v = _np.asarray([vector], dtype=_np.float32)
            _faiss.normalize_L2(v)
            self._faiss.add(v)
        else:
            self._dirty = True

    def remove(self, entry_id: str) -> None:
        idx = self._pos.pop(entry_id, None)
        if idx is None:
            return
        self._ids.pop(idx)
        self._vectors.pop(idx)
        for i in range(idx, len(self._ids)):
            self._pos[self._ids[i]] = i
        self._invalidate()

    def search(self, query: Sequence[float], top_k: int = 32) -> list[tuple[str, float]]:
        if not self._ids or not query or len(query) != self._dim:
            return []
        k = min(top_k, len(self._ids))

        if self._faiss is not None:
            v = _np.asarray([query], dtype=_np.float32)
            _faiss.normalize_L2(v)
            scores, indices = self._faiss.search(v, k)
            return [
                (self._ids[int(i)], float(s))
                for s, i in zip(scores[0], indices[0])
                if i >= 0
            ]

        if _np is not None:
            if self._matrix is None or self._dirty:
                m = _np.asarray(self._vectors, dtype=_np.float32)
                norms = _np.linalg.norm(m, axis=1, keepdims=True)
                norms[norms == 0] = 1.0
                self._matrix = m / norms
                self._dirty = False
            q = _np.asarray(query, dtype=_np.float32)
            qn = float(_np.linalg.norm(q))
            if qn == 0:
                return []
            scores = self._matrix @ (q / qn)
            top = _np.argpartition(scores, -k)[-k:]
            top = top[_np.argsort(scores[top])[::-1]]
            return [(self._ids[int(i)], float(scores[int(i)])) for i in top]

        scored = [
            (entry_id, _cosine(query, vec))
            for entry_id, vec in zip(self._ids, self._vectors)
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]

    def _invalidate(self) -> None:
        self._dirty = True
        if _faiss is not None and _np is not None and self._vectors:
            self._faiss = _faiss.IndexFlatIP(self._dim)
            mat = _np.asarray(self._vectors, dtype=_np.float32)
            _faiss.normalize_L2(mat)
            self._faiss.add(mat)
        else:
            self._faiss = None
