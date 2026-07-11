"""AWS Bedrock + InferCache example.

Prerequisites:
  pip install "infercache[bedrock]"
  AWS credentials configured (aws configure, or IAM role on EC2/Lambda)

Run:
  python examples/bedrock_example.py
"""

from infercache import CacheConfig, InferCache
from infercache.integrations.adapters import BedrockAdapter

cache = InferCache(
    CacheConfig(
        similarity_threshold=0.55,
        ttl_seconds=3600,
        backend="memory",  # use backend="redis" in production
    )
)

adapter = BedrockAdapter(
    cache=cache,
    default_model="anthropic.claude-3-5-sonnet-20241022-v2:0",
    region_name="us-east-1",
)

messages = [
    {"role": "system", "content": "You are a helpful assistant. Be brief."},
    {"role": "user", "content": "What is semantic caching in one sentence?"},
]

print("--- First call (hits Bedrock) ---")
r1 = adapter.chat(messages)
print("Cache hit:", r1["cache_hit"])
print("Response:", r1["response"][:200])

print("\n--- Second call (cache hit, no Bedrock charge) ---")
r2 = adapter.chat(messages)
print("Cache hit:", r2["cache_hit"])

print("\nStats:", cache.stats())
