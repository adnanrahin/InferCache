"""Configuration package."""

from infercache.config.paths import data_dir, default_cache_path
from infercache.config.settings import CacheConfig

__all__ = ["CacheConfig", "data_dir", "default_cache_path"]
