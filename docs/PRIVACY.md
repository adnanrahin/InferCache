# Local-First Architecture

InferCache is designed so that **nothing leaves the user's computer** except the
LLM calls they were already making. There is no hosted service, no cluster to
run, no telemetry, and no account.

## Guarantees

| Component | Where it runs | Network access |
|-----------|---------------|----------------|
| Cache storage (SQLite) | `~/.infercache/cache.db` on the user's disk | None |
| Cache storage (memory) | Process RAM | None |
| Embeddings (TF-IDF / hash) | Computed locally in pure Python | None — no embedding API calls |
| Semantic similarity | Local CPU | None |
| Prompt optimization | Local CPU | None |
| MCP server | Local process, stdio only | None |
| Gateway | Binds `127.0.0.1` by default | Outbound **only** to the LLM upstream the user configures |
| Metrics / stats | In-process counters | None — never uploaded |

## What InferCache never does

- No telemetry, analytics, or "phone home" of any kind
- No embedding API calls — similarity uses local TF-IDF + lexical matching,
  so prompts are never sent anywhere for vectorization
- No hosted cache — there is no InferCache server to sign up for
- No required external services — Redis support exists **only** as an opt-in
  for teams that already run their own; SQLite is the default and needs nothing

## Where your data lives

```
~/.infercache/
└── cache.db        # SQLite: prompts, responses, embeddings, hit counts
```

- Override the location with the `INFERCACHE_HOME` environment variable
- Delete everything at any time: `infercache clear`, or just delete the folder
- Entries expire automatically via TTL (default 1 hour)

## Network behavior in detail

The **only** outbound connections InferCache ever makes are the LLM requests
your application was already going to make:

```
cache MISS → your configured upstream (OpenAI / Anthropic / Bedrock / Ollama)
cache HIT  → zero network traffic; answered from local disk
```

With a local model (Ollama on your machine or LAN), the entire system —
cache, embeddings, inference — runs without touching the internet.

## Verifying these claims

This is an open-source project; the codebase is small enough to audit:

- `src/infercache/embeddings/` — no imports of `urllib`/`requests`/sockets
- `src/infercache/storage/sqlite.py` — stdlib `sqlite3` only
- `src/infercache/gateway/server.py` — the only file that makes outbound
  requests, and only to `openai_upstream` / `anthropic_upstream` you set
- Zero runtime dependencies in `pyproject.toml` (`dependencies = []`)

```bash
# Prove it: grep for network imports outside the gateway/adapters
grep -r "urlopen\|requests\|httpx" src/infercache --include="*.py"
```
