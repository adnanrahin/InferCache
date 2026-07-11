"""Local data paths — everything lives in the user's home directory."""

from __future__ import annotations

import os
from pathlib import Path


def data_dir() -> Path:
    """Per-user InferCache data directory (override with INFERCACHE_HOME)."""
    root = os.environ.get("INFERCACHE_HOME")
    path = Path(root) if root else Path.home() / ".infercache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_cache_path() -> str:
    """Default SQLite cache location: ~/.infercache/cache.db"""
    return str(data_dir() / "cache.db")
