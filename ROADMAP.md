# InferCache Roadmap — "The best LLM cache in the world"

> **Mission:** Make InferCache the default caching + inference-optimization layer for every
> LLM application — local-first, provider-agnostic, provably safe, and fast enough to sit
> in the hot path of production traffic.

This document is the **north star**. The concrete, agent-executable work items live in
[`docs/plan/`](docs/plan/) — each file is a self-contained spec another agent can implement
end to end. Start with [`docs/plan/00-overview.md`](docs/plan/00-overview.md).

---

## 1. Where we are today (v0.2.1)

InferCache is already a real, working two-tier cache:

- **Exact + semantic lookup** (BLAKE2b keys → embedding ANN with margin-based accept rules)
- **Pluggable embeddings** (TF-IDF default, hash, optional MiniLM) + local vector index (FAISS/NumPy/pure-Python)
- **Storage backends** (SQLite default, memory, Redis)
- **Delivery surfaces**: Python library, decorator, CLI, MCP server (Cursor-tested), caching gateway (Ollama-tested), FastAPI example
- **Provider adapters**: OpenAI, Anthropic, Bedrock, Ollama, llama.cpp, generic
- **Adaptive thresholds, prompt optimization, model cascade, metrics, benchmark harness**

**Tested end-to-end:** Ollama adapter, Cursor MCP, gateway (Ollama upstream), FastAPI (Ollama).

### The honest gaps (what stops us being "the best")

| Theme | Representative problems (from code audit) |
|-------|-------------------------------------------|
| **Correctness / safety** | Semantic false positives; adaptive stats in-memory only; no per-entry invalidation; no negative caching; vector index goes stale after TTL eviction; scope match is exact-equality only |
| **Performance / scale** | O(n) fallback scans; blocking `urlopen` everywhere; global gateway `RLock`; persistent metrics commit on every hit/miss; FAISS full rebuild on update; TF-IDF hash collisions |
| **Provider coverage** | No Gemini / Vertex / Azure OpenAI / Cohere / Mistral / Groq; tool-calls, multimodal, logprobs, and streaming for Anthropic are dropped; sampling params not scoped in adapters |
| **Observability** | Heuristic token counts (not provider usage); no time-series; no OpenTelemetry; no per-model/day breakdown |
| **Security** | Gateway & MCP have no auth; plaintext prompts/responses at rest; no PII redaction; no secret scanning in CI |
| **Developer experience** | No first-class LangChain / LlamaIndex integration; no async API; no typed SDK story |
| **Quality bar** | CI is pytest-only — no ruff lint gate, no mypy, no coverage threshold, no security scan, no benchmark regression; ~22 modules untested |

---

## 2. Product principles (non-negotiable)

1. **Local-first, zero mandatory cloud.** Everything must work offline with stdlib-only defaults.
2. **Safety over hit-rate.** A wrong cache hit is worse than a miss. Every semantic hit must be
   defensible with a calibrated confidence and be overridable/invalidatable.
3. **Zero-config good, full-config great.** Sensible defaults; every knob documented.
4. **Provider-agnostic by contract.** One internal request/response schema; providers are adapters.
5. **Observable by default.** You can always answer "why was this a hit/miss, and what did it save?"
6. **No secrets, ever, in the repo or logs.** (Enforced in CI.)
7. **Backward compatible.** Public API changes go through deprecation shims (the repo already uses this pattern in `cache.py`, `adapters.py`).

---

## 3. Success metrics (how we know we won)

| Dimension | Today (approx) | Target |
|-----------|----------------|--------|
| Semantic **false-positive rate** (labeled eval set) | unmeasured | **< 1%** at reported hit-rate |
| p50 / p99 **lookup latency** (100k entries, warm) | unmeasured; O(n) risk | **< 1 ms / < 10 ms** |
| **Providers** supported (first-class, tested) | 2 tested / 6 coded | **10+ tested** |
| **Streaming** cache correctness | OpenAI only | **All streaming providers** incl. tool calls |
| **Test coverage** (line) | no gate | **≥ 85%** enforced |
| **CI gates** | pytest only | pytest + ruff + mypy + coverage + security + benchmark regression |
| **Cold-start** import time | unmeasured | **< 150 ms** with stdlib defaults |
| Token/cost accounting error vs provider usage | heuristic | **< 5%** when provider usage available |

Each spec in `docs/plan/` restates the metrics it moves.

---

## 4. Phased plan

Phases are ordered by **risk-adjusted leverage**. Ship each phase behind tests before moving on.
Every phase maps to one or more specs in `docs/plan/`.

### Phase 0 — Quality foundation (unblocks everything)
*Spec: [`07-quality-and-ci.md`](docs/plan/07-quality-and-ci.md)*
- Ruff lint + format gate, mypy (strict on `core/`), coverage ≥ 85% gate, `pip-audit`/Bandit, benchmark regression job.
- Test the untested: OpenAI/Anthropic/Generic adapters, Redis, embeddings/factory, CLI.
- **Why first:** you cannot safely refactor the hot path without a real quality net.

### Phase 1 — Correctness & safety (the moat)
*Spec: [`01-correctness-and-safety.md`](docs/plan/01-correctness-and-safety.md)*
- Persist adaptive thresholds; calibrated confidence score on every hit; negative/again-caching guardrails.
- Per-entry + tag-based **invalidation API**; keep vector index consistent on eviction/delete.
- Labeled **semantic eval harness** + published false-positive rate.
- **Why:** safety is the single biggest differentiator and the thing enterprises block on.

### Phase 2 — Performance & scale (hot-path ready)
*Spec: [`02-performance-and-scale.md`](docs/plan/02-performance-and-scale.md)*
- Remove O(n) fallbacks; persistent + incremental ANN (hnswlib/faiss) with disk snapshot.
- Async core + non-blocking IO + connection pooling; sharded locks; batched metric writes.
- Import-time budget + lazy provider imports.

### Phase 3 — Provider coverage & fidelity (works everywhere)
*Spec: [`03-provider-coverage.md`](docs/plan/03-provider-coverage.md)*
- Unified internal message schema; adapters for Gemini, Vertex, Azure OpenAI, Cohere, Mistral, Groq.
- Cache **tool calls, multimodal, logprobs**; Anthropic streaming; sampling-param scoping everywhere.

### Phase 4 — Observability (prove the value)
*Spec: [`04-observability.md`](docs/plan/04-observability.md)*
- Provider-reported token/cost accounting; time-series metrics; OpenTelemetry traces/metrics; live dashboard.

### Phase 5 — Security & multi-tenant (enterprise-ready)
*Spec: [`05-security.md`](docs/plan/05-security.md)*
- Gateway/MCP auth (API keys), optional at-rest encryption, PII redaction hooks, per-tenant isolation & quotas.

### Phase 6 — Developer experience & ecosystem (adoption)
*Spec: [`06-developer-experience.md`](docs/plan/06-developer-experience.md)*
- Async-first public API, LangChain + LlamaIndex integrations, typed examples, docs site, cookbook.

---

## 5. Target architecture (end state)

```
                         ┌──────────────────────────────────────────────┐
   Clients / SDKs        │                InferCache                     │
   (OpenAI SDK,          │                                              │
    LangChain,           │   ┌────────────┐   ┌───────────────────────┐ │
    LlamaIndex,   ──────▶│   │  Surfaces  │──▶│      Cache Core       │ │
    MCP, curl)           │   │ gateway /  │   │ normalize → exact →   │ │
                         │   │ mcp / lib /│   │ semantic(ANN+rescore) │ │
                         │   │ decorator  │   │ → confidence gate     │ │
                         │   └────────────┘   └───────────┬───────────┘ │
                         │                                 │             │
                         │   ┌───────────────┐   ┌─────────▼──────────┐ │
                         │   │  Adapters     │   │  Pluggable layers  │ │
                         │   │ OpenAI/Azure/ │   │ embeddings │ index │ │
                         │   │ Anthropic/    │   │ storage    │ metrics│ │
                         │   │ Gemini/Vertex/│   │ redaction  │ policy │ │
                         │   │ Bedrock/Cohere│   └────────────────────┘ │
                         │   │ /Mistral/Groq/│                          │
                         │   │ Ollama/llama  │   observability: OTel     │
                         │   └───────┬───────┘   security: auth/crypto   │
                         └───────────┼──────────────────────────────────┘
                                     ▼
                          Upstream LLM providers
```

---

## 6. How to execute this (for the implementing agent)

1. Read [`docs/plan/00-overview.md`](docs/plan/00-overview.md) — conventions, branch/PR strategy, Definition of Done.
2. Do **Phase 0** first. Do not refactor the hot path until the quality net exists.
3. Take one spec at a time. Each spec lists: context → problem → files → tasks → acceptance criteria → tests.
4. One spec ≈ one PR (or a small stack). Every PR must pass the Phase 0 gates.
5. Update the spec's checklist and this roadmap's status table as you land work.

## 7. Status tracker

| Phase | Spec | Status |
|-------|------|--------|
| 0 | Quality & CI | ☐ Not started |
| 1 | Correctness & safety | ☐ Not started |
| 2 | Performance & scale | ☐ Not started |
| 3 | Provider coverage | ☐ Not started |
| 4 | Observability | ☐ Not started |
| 5 | Security & multi-tenant | ☐ Not started |
| 6 | Developer experience | ☐ Not started |

_Last updated: 2026-09-07._
