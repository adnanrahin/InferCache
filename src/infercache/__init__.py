"""InferCache: multi-tier LLM caching and token optimization."""

from infercache.__version__ import __version__
from infercache.config import CacheConfig
from infercache.core import InferCache
from infercache.integrations import cached_llm_call, configure
from infercache.metrics import CacheMetrics
from infercache.optimization import PromptOptimizer
from infercache.routing import CascadeStage, ModelCascade

__all__ = [
    "InferCache",
    "CacheConfig",
    "CacheMetrics",
    "PromptOptimizer",
    "CascadeStage",
    "ModelCascade",
    "cached_llm_call",
    "configure",
    "__version__",
]
