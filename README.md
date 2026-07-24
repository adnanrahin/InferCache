# InferCache

**Local-first LLM caching and token optimization** — target **20%+ token cost reduction** through semantic caching, prompt compression, and prefix optimization.

**Everything runs on your machine.** Cache lives in `~/.infercache/cache.db` (SQLite), embeddings are computed locally, there is no telemetry, no hosted service, and nothing to sign up for. See [docs/PRIVACY.md](docs/PRIVACY.md).

**New here?** Start with **[docs/GETTING_STARTED.md](docs/GETTING_STARTED.md)** — clone/pip install, MCP, gateway, library, and CLI, step by step.

Install from wheel:

```bash
pip install infercache
# or with provider adapters:
pip install "infercache[openai,anthropic,redis]"
```

Build locally:

```bash
pip install build
python -m build
pip install dist/infercache-*.whl
```

## Why InferCache?

LLM API costs scale with tokens. Research shows:

- **31%** of production queries are semantically similar to prior requests
- **Semantic caching** can eliminate **20–68%** of API calls ([GPT Semantic Cache](https://arxiv.org/abs/2411.05276))
- **Prompt compression** can reduce input tokens **2–20×** ([LLMLingua](https://arxiv.org/abs/2310.05736))
- **Prefix caching** saves **50–90%** on repeated static context ([Anthropic](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching), [OpenAI](https://platform.openai.com/docs/guides/prompt-caching))

InferCache combines these layers in one installable library.

See [docs/RESEARCH.md](docs/RESEARCH.md) for the full paper bibliography.
See [docs/PACKAGE_STRUCTURE.md](docs/PACKAGE_STRUCTURE.md) for the module layout.

## Quick Start

```python
from infercache import InferCache, CacheConfig

cache = InferCache(CacheConfig(similarity_threshold=0.85))

def my_llm(prompt: str) -> str:
    # Your OpenAI, Anthropic, local model, etc.
    return call_your_llm(prompt)

# First call hits LLM; subsequent similar calls return cached response
result = cache.get_or_call("What is the capital of France?", my_llm)
print(result["response"], result["cache_hit"])

# Paraphrased query — semantic cache hit
result2 = cache.get_or_call("Tell me France's capital.", my_llm)
print(result2["cache_hit"])  # True

print(cache.stats())
```

## Decorator API

```python
from infercache import cached_llm_call

@cached_llm_call(model="gpt-4o-mini")
def chat(prompt: str) -> str:
    return openai_client.chat.completions.create(...).choices[0].message.content
```

## Chat Messages (Multi-turn)

```python
messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Explain caching."},
]

result = cache.get_or_call_messages(messages, lambda msgs: my_chat_api(msgs))
optimized = result.get("optimized_messages")  # pruned + compressed
```

## Provider Adapters

```python
from infercache.integrations.adapters import OpenAIAdapter, AnthropicAdapter, GenericAdapter

# OpenAI (pip install infercache[openai])
adapter = OpenAIAdapter(default_model="gpt-4o-mini")
result = adapter.chat([{"role": "user", "content": "Hello"}])

# Anthropic with cache_control hints
adapter = AnthropicAdapter()
result = adapter.chat(messages, system="Long static system prompt...")

# Any LLM function
adapter = GenericAdapter()
result = adapter.complete("prompt", my_llm_fn)
```

## VS Code / IDE Integration

Use InferCache as a middleware layer in your backend or extension:

### Option 1: Python backend proxy

```python
# server.py — run alongside your chat extension
from flask import Flask, request, jsonify
from infercache import InferCache

app = Flask(__name__)
cache = InferCache()

@app.post("/chat")
def chat():
    prompt = request.json["prompt"]
    result = cache.get_or_call(prompt, your_llm_function)
    return jsonify(result)
```

Point your VS Code extension or Copilot-style tool at `http://localhost:5000/chat`.

### Option 2: Drop-in wrapper

```python
# In your existing LLM service module
from infercache.integrations import configure, cached_llm_call
from infercache import CacheConfig

configure(CacheConfig(similarity_threshold=0.85, ttl_seconds=3600))

@cached_llm_call(model="default")
def generate(prompt: str) -> str:
    ...
```

### Option 3: CLI for testing

```bash
infercache store "What is Python?" "Python is a programming language."
infercache lookup "Tell me about Python."
infercache benchmark --queries 100 --repeat-rate 0.4
infercache stats
```

## MCP Server (Cursor / Claude Desktop / Claude Code)

Expose the cache as MCP tools any AI client can call — full setup in [docs/MCP.md](docs/MCP.md):

```bash
infercache mcp
```

Register in Cursor (`.cursor/mcp.json`) or Claude Desktop:

```json
{
  "mcpServers": {
    "infercache": { "command": "infercache", "args": ["mcp"] }
  }
}
```

Tools: `cache_lookup`, `cache_store`, `cache_stats`, `cache_feedback`, `cache_clear`.
All clients share the same local SQLite cache.

## Caching Gateway (transparent proxy)

Point any OpenAI/Anthropic-compatible client at the gateway and get caching with zero code changes:

```bash
# Cache in front of OpenAI (or Ollama's OpenAI-compatible endpoint)
infercache gateway --port 8899 --openai-upstream https://api.openai.com

# Then set your client's base URL to http://127.0.0.1:8899/v1
```

Works with SDKs, Claude Code (`ANTHROPIC_BASE_URL=http://127.0.0.1:8899`), LiteLLM, and local Ollama (`--openai-upstream http://192.168.1.248:11434`).

## Benchmarking

```bash
infercache benchmark --queries 500 --repeat-rate 0.4 --model gpt-4o-mini --output report.md
```

Measures hit rate, hit/miss latency (avg + p95), tokens saved, and dollars saved using per-model pricing. Bring your own workload with `--dataset prompts.jsonl`.

## Configuration

```python
from infercache import CacheConfig

config = CacheConfig(
    similarity_threshold=0.55,      # Semantic match threshold
    adaptive_threshold=True,          # VectorQ/vCache-style adaptation
    enable_prompt_compression=True,   # LLMLingua-inspired compression
    compression_ratio=0.7,            # Keep ~70% of content
    enable_history_pruning=True,
    max_history_messages=10,
    enable_prefix_optimization=True,  # Static-first for provider caching
    ttl_seconds=3600,
    backend="sqlite",                 # local-first default for CLI/MCP/gateway;
                                      # "memory" (per-process) or opt-in "redis"
    use_vector_index=True,            # local ANN over embeddings
    persist_metrics=True,             # hit/miss counters in SQLite
    embedding_model="tfidf",          # or "minilm" with infercache[semantic]
    semantic_score_margin=0.02,       # refuse ambiguous near-ties
)
```

## Model cascade (cheap → expensive)

```python
from infercache import CascadeStage, InferCache, ModelCascade

cascade = ModelCascade(cache, [
    CascadeStage("small", cheap_fn),
    CascadeStage("big", expensive_fn),
])
result = cascade.complete("Explain caching briefly")
```

## Architecture

```
Request → [Prompt Optimizer] → [Exact Cache] → [Semantic Cache] → [Cascade?] → LLM API
                ↓                      ↓ hit              ↓ hit
         compression            return response    return response
         history prune
         prefix reorder
```

## Metrics

```python
stats = cache.stats()
# {
#   "hit_rate": 0.42,
#   "token_reduction_pct": 28.5,
#   "estimated_cost_reduction_pct": 31.2,
#   "tokens_saved": 15420,
#   ...
# }
```

## Storage Backends

| Backend | Persistence | Requires | Default for |
|---------|-------------|----------|-------------|
| `sqlite` | `~/.infercache/cache.db` | Nothing (stdlib) | CLI, MCP, gateway |
| `memory` | Process lifetime | Nothing | Library embedding |
| `redis` | External server | Your own Redis (opt-in only) | Multi-server teams |

No hosted service or cluster is ever required — SQLite covers local use completely.

## Development

```bash
pip install -e ".[dev]"
pytest
python -m build
```

## License

MIT — see [LICENSE](LICENSE).
