# Package Structure

```
src/infercache/
├── __init__.py              # Public API
├── __version__.py
├── cache.py                 # Shim → core.engine (backward compat)
├── optimizer.py             # Shim → optimization.optimizer
├── tokens.py                # Shim → optimization.tokens
├── wrapper.py               # Shim → integrations.wrapper
├── adapters.py              # Shim → integrations.adapters
│
├── config/                  # Configuration
│   ├── __init__.py
│   └── settings.py          # CacheConfig
│
├── core/                    # Caching engine
│   ├── __init__.py
│   ├── adaptive.py          # Adaptive thresholds (VectorQ/vCache)
│   ├── engine.py            # InferCache main class
│   ├── keys.py              # Exact cache key generation
│   ├── lookup.py            # Exact + semantic lookup
│   └── store.py             # Cache persistence
│
├── embeddings/              # Semantic similarity
│   ├── __init__.py
│   ├── base.py              # EmbeddingBackend + text_similarity
│   ├── factory.py
│   ├── hash.py
│   └── tfidf.py
│
├── storage/                 # Cache backends
│   ├── __init__.py
│   ├── base.py
│   ├── factory.py
│   ├── memory.py
│   ├── models.py            # CacheEntry
│   └── redis.py
│
├── optimization/            # Token reduction
│   ├── __init__.py
│   ├── optimizer.py         # PromptOptimizer
│   └── tokens.py            # Token estimation
│
├── metrics/                 # Savings tracking
│   ├── __init__.py
│   └── collector.py         # CacheMetrics
│
├── integrations/            # LLM provider hooks
│   ├── __init__.py
│   ├── wrapper.py           # @cached_llm_call decorator
│   └── adapters/
│       ├── __init__.py
│       ├── base.py
│       ├── openai.py
│       ├── anthropic.py
│       └── generic.py
│
└── cli/                     # Command-line tools
    ├── __init__.py
    ├── benchmark.py
    └── main.py
```

## Import Guide

| Use case | Import |
|----------|--------|
| Quick start | `from infercache import InferCache, CacheConfig` |
| Core engine | `from infercache.core import InferCache` |
| Config | `from infercache.config import CacheConfig` |
| Embeddings | `from infercache.embeddings import TfidfEmbedding` |
| Storage | `from infercache.storage import MemoryStorage, RedisStorage` |
| Optimization | `from infercache.optimization import PromptOptimizer` |
| Metrics | `from infercache.metrics import CacheMetrics` |
| Decorator | `from infercache.integrations import cached_llm_call` |
| OpenAI | `from infercache.integrations.adapters import OpenAIAdapter` |
| CLI | `infercache benchmark` |

## Tests

```
tests/
├── core/test_engine.py
├── optimization/test_optimizer.py
├── embeddings/test_similarity.py
└── cli/test_benchmark.py
```
