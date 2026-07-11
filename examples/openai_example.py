"""OpenAI integration example — requires infercache[openai] and OPENAI_API_KEY."""

from infercache import CacheConfig, InferCache
from infercache.integrations.adapters import OpenAIAdapter

cache = InferCache(CacheConfig(similarity_threshold=0.85))
adapter = OpenAIAdapter(cache=cache)

messages = [{"role": "user", "content": "Say hello in one sentence."}]
result = adapter.chat(messages)
print("Cache hit:", result.get("cache_hit"))
print("Response:", result.get("response"))
print("Stats:", cache.stats())
