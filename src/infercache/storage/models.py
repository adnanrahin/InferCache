"""Cache entry model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class CacheEntry:
    key: str
    prompt: str
    response: str
    embedding: list[float] | None
    created_at: float
    hits: int = 0
    metadata: dict[str, Any] | None = None
    adaptive_threshold: float | None = None
