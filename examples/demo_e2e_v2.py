"""
End-to-end demo: InferCache v0.2 + Ollama

Shows:
  - exact + semantic cache hits
  - cascade (optional second model)
  - tokens spent vs saved

Run:
  conda activate infer_cache
  OLLAMA_HOST=127.0.0.1:11434 OLLAMA_MODEL=qwen3.5:latest python examples/demo_e2e_v2.py

Optional stronger embeddings (local):
  pip install "infercache[semantic]"
  OLLAMA_HOST=127.0.0.1:11434 EMBEDDING=minilm python examples/demo_e2e_v2.py
"""

from __future__ import annotations

import os
import time

from infercache import CacheConfig, CascadeStage, InferCache, ModelCascade
from infercache.integrations.adapters import OllamaAdapter
from infercache.optimization.tokens import estimate_tokens

OLLAMA_URL = os.environ.get("OLLAMA_HOST", "127.0.0.1:11434")
MODEL = os.environ.get("OLLAMA_MODEL", "qwen3.5:latest")
EMBEDDING = os.environ.get("EMBEDDING", "tfidf")  # or minilm


def main() -> None:
    print("=" * 64)
    print("InferCache v0.2 end-to-end demo")
    print("=" * 64)

    config = CacheConfig(
        backend="sqlite",
        similarity_threshold=0.55,
        semantic_score_margin=0.02,
        use_vector_index=True,
        persist_metrics=True,
        embedding_model=EMBEDDING,
        ttl_seconds=3600,
    )
    try:
        cache = InferCache(config)
    except ImportError as exc:
        print(f"Embedding backend '{EMBEDDING}' unavailable: {exc}")
        print("Falling back to tfidf")
        config.embedding_model = "tfidf"
        cache = InferCache(config)

    adapter = OllamaAdapter(cache=cache, base_url=OLLAMA_URL, default_model=MODEL)
    print(f"Ollama     : {adapter.base_url}")
    print(f"Model      : {MODEL}")
    print(f"Embeddings : {cache.config.embedding_model}")
    try:
        print(f"Models     : {adapter.list_models()}")
    except ConnectionError as exc:
        print(f"ERROR: {exc}")
        return

    spent = saved = 0
    prompts = [
        "Explain what a cache is in one short sentence.",
        "Explain what a cache is in one short sentence.",  # exact hit
        "In one sentence, what does caching mean?",  # semantic hit
        "Name one benefit of caching LLM responses.",
        "Name one benefit of caching LLM responses.",  # exact hit
    ]

    print("\n--- Cache path ---")
    for i, prompt in enumerate(prompts, 1):
        t0 = time.perf_counter()
        out = adapter.chat([{"role": "user", "content": prompt}])
        ms = (time.perf_counter() - t0) * 1000
        toks = estimate_tokens(prompt) + estimate_tokens(out.get("response", ""))
        hit = bool(out.get("cache_hit"))
        if hit:
            saved += toks
            path = "HIT"
        else:
            spent += toks
            path = "MISS"
        print(f"{i}. {path:4}  {ms:7.0f}ms  ~{toks} tok  {prompt[:50]!r}")

    print("\n--- Cascade path (cheap model first) ---")

    def call_model(p: str) -> str:
        return adapter._generate_uncached(p, MODEL)

    # Single-stage cascade still exercises the API; add a stub escalate stage
    cascade = ModelCascade(
        cache,
        [
            CascadeStage(MODEL, call_model),
        ],
    )
    c1 = cascade.complete("Say OK in one word.")
    print(f"cascade cache_hit={c1.get('cache_hit')} model={c1.get('model_used')}")

    total = spent + saved
    pct = (100.0 * saved / total) if total else 0.0
    print("\n" + "=" * 64)
    print("TOKEN REPORT")
    print(f"  SPENT  : ~{spent}")
    print(f"  SAVED  : ~{saved}")
    print(f"  RATE   : {pct:.1f}%")
    print("Stats:", cache.stats())
    print("=" * 64)


if __name__ == "__main__":
    main()
