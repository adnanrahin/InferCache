"""Ollama + InferCache example (local or remote server).

Prerequisites:
  1. Ollama running on a reachable host
  2. A model pulled on that server, e.g. ollama pull llama3.2

Remote server (your machine → 192.168.1.248):
  set OLLAMA_HOST=192.168.1.248:11434
  python examples/ollama_example.py

Or pass base_url directly in code (see below).

On the Ollama server, ensure it listens on the network:
  set OLLAMA_HOST=0.0.0.0:11434
  ollama serve
"""

import os

from infercache import CacheConfig, InferCache
from infercache.integrations.adapters import OllamaAdapter

# Remote Ollama — pick one:
#   Option A: environment variable
#     set OLLAMA_HOST=192.168.1.248:11434
#   Option B: pass base_url directly
OLLAMA_URL = os.environ.get("OLLAMA_HOST", "192.168.1.248:11434")

cache = InferCache(CacheConfig(similarity_threshold=0.55, ttl_seconds=3600))
adapter = OllamaAdapter(cache=cache, base_url=OLLAMA_URL, default_model="llama3.2")

print(f"Ollama server: {adapter.base_url}")
print("Available models:", adapter.list_models())

messages = [{"role": "user", "content": "Say hello in one short sentence."}]

print("\n--- First call (hits Ollama) ---")
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
