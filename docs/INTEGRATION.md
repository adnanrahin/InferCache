# Integration Guide

How to use InferCache as a package in your application, with AWS Bedrock, Ollama, and Cursor.

## Mental model

InferCache is **middleware**, not a replacement for your LLM provider.

```
Your App  →  InferCache  →  LLM (Bedrock / Ollama / OpenAI)
                ↓
           cache store (memory or Redis)
```

You install the wheel, wrap LLM calls, and InferCache automatically saves on miss and returns on hit.

## Install

```bash
pip install infercache
# or with provider extras:
pip install "infercache[bedrock]"
pip install "infercache[openai,anthropic,redis]"
```

From local wheel:

```bash
pip install dist/infercache-0.1.0-py3-none-any.whl
```

---

## Pattern 1: Adapter (simplest)

Use a built-in adapter for your LLM provider.

### AWS Bedrock

```python
from infercache import CacheConfig, InferCache
from infercache.integrations.adapters import BedrockAdapter

cache = InferCache(CacheConfig(ttl_seconds=3600))
bedrock = BedrockAdapter(
    cache=cache,
    region_name="us-east-1",
    default_model="anthropic.claude-3-5-sonnet-20241022-v2:0",
)

messages = [{"role": "user", "content": "Summarize semantic caching."}]
result = bedrock.chat(messages)

print(result["response"])
print(result["cache_hit"])  # False first time, True on repeat
```

Requires: `pip install "infercache[bedrock]"` and AWS credentials.

### Ollama (remote or local)

```python
from infercache.integrations.adapters import OllamaAdapter

ollama = OllamaAdapter(
    base_url="192.168.1.248:11434",
    default_model="qwen3.5:latest",
)
result = ollama.chat([{"role": "user", "content": "Hello"}])
```

---

## Pattern 2: Your own API (FastAPI / Flask / Django)

Put InferCache **inside your backend** so all user traffic flows through it.

See `examples/fastapi_app.py`:

```bash
set PROVIDER=bedrock
uvicorn examples.fastapi_app:app --port 8080
```

```bash
curl -X POST http://localhost:8080/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id":"alice","prompt":"What is caching?"}'
```

**Per-user cache isolation** — pass `user_id` as a kwarg; it becomes part of the cache key:

```python
cache.get_or_call(prompt, llm_fn, model="claude-3", user_id=request.user.id)
```

---

## Pattern 3: Decorator on existing functions

Wrap code you already have:

```python
from infercache.integrations import cached_llm_call, configure
from infercache import CacheConfig

configure(CacheConfig(similarity_threshold=0.55))

@cached_llm_call(model="anthropic.claude-3-5-sonnet-20241022-v2:0")
def ask_bedrock(prompt: str) -> str:
    # your existing boto3 bedrock call
    ...
```

---

## Pattern 4: Generic — any LLM

If no adapter exists yet:

```python
from infercache import InferCache
from infercache.integrations.adapters import GenericAdapter

adapter = GenericAdapter()

def my_bedrock(messages):
    return boto3_client.converse(...)["output"]["message"]["content"][0]["text"]

result = adapter.chat(messages, my_bedrock, model="claude-3")
```

---

## Using with Cursor

**Important:** Cursor IDE has its own built-in AI. InferCache does **not** plug into Cursor's chat directly.

You use InferCache in **your project's backend** that Cursor (or any client) calls:

### Option A — Local proxy while developing in Cursor

Run the HTTP proxy from your repo:

```bash
python examples/vscode_backend.py
```

Any tool (including a Cursor task or extension) can POST to `http://127.0.0.1:8765/chat`.

### Option B — Develop the cached API in Cursor, deploy for users

1. Build `fastapi_app.py` (or your own) in this repo using Cursor
2. Deploy to AWS (ECS, Lambda, EC2) with Bedrock + Redis cache
3. Your **users' apps** call **your API** — InferCache runs server-side

```
User's mobile app  →  your-api.com/v1/chat  →  InferCache  →  Bedrock
Cursor (you)       →  edits the Python code that powers the above
```

### Option C — Cursor Agent uses your cached endpoint

Configure a custom MCP server or HTTP tool in Cursor that points to your InferCache-backed API instead of calling Bedrock directly. Cursor sends prompts to your server; your server handles caching.

---

## Production checklist

| Concern | Recommendation |
|---------|----------------|
| Cache storage | `CacheConfig(backend="redis", redis_url="redis://...")` |
| Multi-tenant | Pass `user_id` / `tenant_id` in cache kwargs |
| TTL | `ttl_seconds=3600` (adjust per use case) |
| Sensitive data | Don't cache prompts with PII; use shorter TTL |
| Wrong answers | `cache.feedback(prompt, was_correct=False)` |
| Metrics | `cache.stats()` → export to CloudWatch/Datadog |

---

## What gets saved automatically

On every **cache miss** when using `get_or_call` / adapters:

- Optimized prompt (or messages JSON)
- LLM response text
- Model ID
- Embedding (for semantic matching)
- Any extra kwargs (`user_id`, etc.)

On **cache hit** — nothing new is saved; the existing entry is returned.
