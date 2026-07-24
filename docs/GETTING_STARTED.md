# Getting Started with InferCache

InferCache is **local-first**: cache lives on your machine (`~/.infercache/cache.db`), no hosted Redis/cluster required.

Pick one path below depending on how you want to use it.

---

## Path A — Install from GitHub (clone)

```bash
git clone https://github.com/YOUR_ORG/InferCache.git
cd InferCache

# create / activate an env (conda or venv)
conda create -n infer_cache python=3.11 -y
conda activate infer_cache
# or: python -m venv .venv && source .venv/bin/activate   # Linux/macOS
# or: .\.venv\Scripts\Activate.ps1                        # Windows

# install the package (editable = good for development)
pip install -e .

# optional extras
pip install -e ".[openai,anthropic,bedrock]"
# stronger local embeddings (MiniLM + FAISS when available)
pip install -e ".[semantic]"

# verify
infercache --version
python -c "from infercache import InferCache; print('ok')"
```

Run tests:

```bash
pip install pytest
python -m pytest -q
```

---

## Path B — Install from a wheel file

Someone sends you (or you build) `infercache-0.2.0-py3-none-any.whl`.

```bash
pip install infercache-0.2.0-py3-none-any.whl
# with extras:
pip install "infercache-0.2.0-py3-none-any.whl[openai,anthropic,bedrock,semantic]"

infercache --version
```

**Build a wheel yourself (maintainers):**

```bash
cd InferCache
pip install build
python -m build
# → dist/infercache-0.2.0-py3-none-any.whl
```

---

## Path C — Later: install from PyPI

Once published:

```bash
pip install infercache
# or
pip install "infercache[openai,anthropic,bedrock]"
```

---

## Use case 1 — Python library (in your app)

```python
from infercache import InferCache, CacheConfig

cache = InferCache(CacheConfig(
    backend="sqlite",              # persists to ~/.infercache/cache.db
    similarity_threshold=0.55,
))

def my_llm(prompt: str) -> str:
    # call OpenAI / Bedrock / Ollama / anything
    return call_your_llm(prompt)

result = cache.get_or_call("What is caching?", my_llm, model="my-model")
print(result["response"], result["cache_hit"])
print(cache.stats())
```

Adapters (optional):

```python
from infercache.integrations.adapters import OllamaAdapter, BedrockAdapter, OpenAIAdapter

# Ollama (local / LAN)
ollama = OllamaAdapter(base_url="http://192.168.1.248:11434", default_model="qwen3.5:latest")
print(ollama.chat([{"role": "user", "content": "Hello"}]))

# Bedrock  (pip install "infercache[bedrock]")
bedrock = BedrockAdapter(region_name="us-east-1")
print(bedrock.chat([{"role": "user", "content": "Hello"}]))
```

---

## Use case 2 — CLI (quick local cache)

```bash
# store
infercache store "What is Python?" "Python is a programming language." --model test

# exact lookup
infercache lookup "What is Python?" --model test

# paraphrase / semantic lookup
infercache lookup "Tell me about Python." --model test

# stats / clear
infercache stats
infercache clear

# benchmark token / cost savings
infercache benchmark --queries 100 --repeat-rate 0.4 --model gpt-4o-mini --output report.md
```

Cache file: `~/.infercache/cache.db` (Windows: `C:\Users\<you>\.infercache\cache.db`)

---

## Use case 3 — MCP (Cursor / Claude Desktop / Claude Code)

MCP lets AI clients call cache tools (`cache_lookup`, `cache_store`, …) before spending tokens.

### 1. Install InferCache (Path A or B)

```bash
pip install -e .          # or: pip install infercache-....whl
infercache --version
```

### 2. Smoke-test the MCP server

```bash
infercache mcp
```

Paste this line and press Enter (you should get a JSON reply):

```json
{"jsonrpc":"2.0","id":1,"method":"initialize"}
```

Ctrl+C to stop.

### 3. Register in Cursor

Create `.cursor/mcp.json` in your project (or `~/.cursor/mcp.json` for all projects):

```json
{
  "mcpServers": {
    "infercache": {
      "command": "infercache",
      "args": ["mcp"]
    }
  }
}
```

If `infercache` is not on PATH, use the full Python path:

```json
{
  "mcpServers": {
    "infercache": {
      "command": "C:\\Users\\YOU\\.conda\\envs\\infer_cache\\python.exe",
      "args": ["-m", "infercache.mcp"]
    }
  }
}
```

Reload Cursor → **Settings → MCP** → confirm `infercache` shows 5 tools.

### 4. Claude Desktop

Edit:

- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`

Use the same `mcpServers` JSON as above. Restart Claude Desktop.

### 5. Claude Code

```bash
claude mcp add infercache -- infercache mcp
```

### 6. Optional: tell the agent to use the cache

Create `.cursor/rules/infercache.mdc`:

```
Before answering questions that may repeat, call infercache cache_lookup.
If cache_hit=true, use that response.
After generating a new substantive answer, call cache_store.
```

Full details: [MCP.md](MCP.md)

---

## Use case 4 — Gateway (transparent caching proxy)

Any OpenAI/Anthropic-compatible client can get caching by pointing its **base URL** at InferCache. No code changes in the client.

### 1. Start the gateway

```bash
# In front of OpenAI
infercache gateway --port 8899 --openai-upstream https://api.openai.com

# In front of local/LAN Ollama (OpenAI-compatible API)
infercache gateway --port 8899 --openai-upstream http://192.168.1.248:11434

# In front of Anthropic
infercache gateway --port 8899 --anthropic-upstream https://api.anthropic.com

# Optional: MiniLM embeddings (requires: pip install "infercache[semantic]")
infercache gateway --port 8899 --openai-upstream http://127.0.0.1:11434 --embedding minilm
```

Defaults: binds `127.0.0.1`, SQLite cache at `~/.infercache/cache.db`. On stream misses, SSE is piped live from upstream while the response is cached.

### 2. Point your client at it

**OpenAI Python SDK:**

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8899/v1",
    api_key="sk-...",   # still required by many clients; forwarded upstream
)
print(client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello"}],
))
```

**Ollama via gateway (curl / PowerShell):**

```powershell
$body = @{
  model = "qwen3.5:latest"
  messages = @(@{ role = "user"; content = "Say hello in one sentence." })
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Uri http://127.0.0.1:8899/v1/chat/completions `
  -Method POST -ContentType "application/json" -Body $body
```

Call twice — second response should include `"infercache": {"cache_hit": true}`.

**Claude Code:**

```bash
export ANTHROPIC_BASE_URL=http://127.0.0.1:8899
# then run claude as usual (API key still needed for upstream)
```

### 3. Stats / health

```bash
curl http://127.0.0.1:8899/health
curl http://127.0.0.1:8899/stats
```

---

## Use case 5 — FastAPI / your own HTTP API

```bash
pip install fastapi uvicorn
# edit examples/fastapi_app.py if needed, then:
set PROVIDER=ollama
set OLLAMA_HOST=192.168.1.248:11434
uvicorn examples.fastapi_app:app --port 8080
```

```bash
curl -X POST http://localhost:8080/v1/chat \
  -H "Content-Type: application/json" \
  -d "{\"user_id\":\"alice\",\"prompt\":\"What is caching?\"}"
```

---

## Which path should I use?

| Goal | Use |
|------|-----|
| Build an app in Python | **Library** (Use case 1) |
| Quick local experiments | **CLI** (Use case 2) |
| Cursor / Claude Desktop chat | **MCP** (Use case 3) |
| Zero client code changes (SDKs, tools) | **Gateway** (Use case 4) |
| Multi-user product backend | **FastAPI** (Use case 5) |

You can run **MCP + Gateway** together — both share the same local SQLite cache.

---

## v0.2 extras (vector index, cascade, persistent stats)

```python
from infercache import CacheConfig, CascadeStage, InferCache, ModelCascade

cache = InferCache(CacheConfig(
    backend="sqlite",
    use_vector_index=True,       # local ANN over embeddings
    persist_metrics=True,        # hit/miss counters survive restarts
    embedding_model="tfidf",     # or "minilm" with infercache[semantic]
    semantic_score_margin=0.02,  # refuse ambiguous near-ties
))

# Cheap model first; escalate only when uncertain
cascade = ModelCascade(cache, [
    CascadeStage("small", cheap_fn),
    CascadeStage("big", expensive_fn),
])
print(cascade.complete("Explain caching briefly"))
```

End-to-end Ollama demo:

```bash
OLLAMA_HOST=127.0.0.1:11434 OLLAMA_MODEL=qwen3.5:latest python examples/demo_e2e_v2.py
```

## Privacy reminder

- Cache, embeddings, and MCP: **local only**
- Gateway: outbound **only** to the LLM upstream you configure
- No telemetry, no hosted InferCache service

See [PRIVACY.md](PRIVACY.md).

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `infercache` not found | Activate your env, then `pip install -e .` |
| Tests fail with `No module named infercache` | Use `python -m pytest`, not bare `pytest` from another env |
| CLI store then lookup = miss | Update to latest CLI (uses SQLite by default) |
| MCP not showing in Cursor | Use full path to `python.exe` / `infercache.exe` in `mcp.json`, reload |
| Ollama / gateway timeout | Check upstream: `http://HOST:11434/api/tags` |
