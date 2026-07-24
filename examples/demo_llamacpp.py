"""
End-to-end demo: InferCache + llama.cpp (llama-server)

Prerequisites:
  1. Build/install llama.cpp and get a GGUF model
  2. Start the OpenAI-compatible server:

       llama-server -m /path/to/model.gguf --port 8080

Run:
  conda activate infer_cache
  LLAMACPP_HOST=127.0.0.1:8080 python examples/demo_llamacpp.py

Optional:
  LLAMACPP_MODEL=my-model.gguf
  EMBEDDING=minilm   # needs: pip install "infercache[semantic]"

Or put InferCache gateway in front (any OpenAI client):
  infercache gateway --port 8899 --openai-upstream http://127.0.0.1:8080
"""

from __future__ import annotations

import os
import time

from infercache import CacheConfig, CascadeStage, InferCache, ModelCascade
from infercache.integrations.adapters import LlamaCppAdapter
from infercache.optimization.tokens import estimate_tokens

HOST = os.environ.get("LLAMACPP_HOST", "127.0.0.1:8080")
MODEL = os.environ.get("LLAMACPP_MODEL", "local")
EMBEDDING = os.environ.get("EMBEDDING", "tfidf")


def main() -> None:
    print("=" * 64)
    print("InferCache + llama.cpp demo")
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

    adapter = LlamaCppAdapter(cache=cache, base_url=HOST, default_model=MODEL)
    print(f"llama-server : {adapter.base_url}")
    print(f"Model        : {MODEL}")
    print(f"Embeddings   : {cache.config.embedding_model}")

    if not adapter.health():
        print("ERROR: llama-server not reachable.")
        print("Start with: llama-server -m model.gguf --port 8080")
        return

    try:
        print(f"Models       : {adapter.list_models()}")
    except ConnectionError as exc:
        print(f"WARN: list_models failed: {exc}")

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

    print("\n--- Cascade path ---")

    def call_model(p: str) -> str:
        return adapter._generate_uncached(p, MODEL)

    cascade = ModelCascade(cache, [CascadeStage(MODEL, call_model)])
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
