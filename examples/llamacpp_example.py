"""llama.cpp (llama-server) + InferCache quick example.

Prerequisites:
  llama-server -m model.gguf --port 8080

Run:
  set LLAMACPP_HOST=127.0.0.1:8080
  python examples/llamacpp_example.py
"""

import os

from infercache import CacheConfig, InferCache
from infercache.integrations.adapters import LlamaCppAdapter

HOST = os.environ.get("LLAMACPP_HOST", "127.0.0.1:8080")
MODEL = os.environ.get("LLAMACPP_MODEL", "local")

cache = InferCache(CacheConfig(similarity_threshold=0.55, ttl_seconds=3600, backend="sqlite"))
adapter = LlamaCppAdapter(cache=cache, base_url=HOST, default_model=MODEL)

print(f"llama-server: {adapter.base_url}")
if not adapter.health():
    print("ERROR: cannot reach llama-server. Start: llama-server -m model.gguf --port 8080")
    raise SystemExit(1)

print("Models:", adapter.list_models())

messages = [{"role": "user", "content": "Say hello in one short sentence."}]

print("\n--- First call (hits llama.cpp) ---")
r1 = adapter.chat(messages)
print("Cache hit:", r1["cache_hit"])
print("Response:", r1["response"])

print("\n--- Second call (cache hit) ---")
r2 = adapter.chat(messages)
print("Cache hit:", r2["cache_hit"])
print("Response:", r2["response"])

print("\n--- Paraphrase (semantic cache hit) ---")
r3 = adapter.chat([{"role": "user", "content": "Greet me briefly in one sentence."}])
print("Cache hit:", r3["cache_hit"])
print("Response:", r3["response"])

print("\nStats:", cache.stats())
