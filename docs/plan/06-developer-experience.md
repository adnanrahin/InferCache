# Spec 06 — Developer Experience & Ecosystem (Phase 6, adoption)

> **Goal:** Make InferCache the easiest cache to adopt: an async-first public API, first-class
> LangChain and LlamaIndex integrations, a typed and documented surface, a docs site, and a cookbook.

**Metrics moved:** time-to-first-cache-hit for a new user minutes not hours; framework users adopt with
< 5 lines; async supported natively; docs discoverable.

## Context (current behavior)
- Public API is synchronous only (`InferCache.get_or_call`, decorator `cached_llm_call`).
- No official LangChain/LlamaIndex integration (users hand-wrap `get_or_call_messages`).
- Docs are good but scattered across `docs/*.md`; no rendered site; no async story; no cookbook.
- Compat shims exist (`cache.py`, `adapters.py`, etc.) and must be preserved.

## Problem
Adoption is gated by integration friction. Framework users and async apps need drop-in support and
clear, typed, discoverable docs.

## Files to touch
- `core/aengine.py` or async methods on `InferCache` — `alookup`, `astore`, `aget_or_call*`.
- `integrations/wrapper.py` — async decorator support (`cached_llm_call` handling coroutines).
- `integrations/langchain/` — **new**: `InferCacheLLMCache` (LangChain `BaseCache`) + a wrapping chat model.
- `integrations/llamaindex/` — **new**: cache wrapper for LlamaIndex LLM calls.
- `pyproject.toml` — extras `[langchain]`, `[llamaindex]`, `[async]` (httpx/aiohttp if needed).
- `examples/` — new runnable examples (LangChain+Ollama, LlamaIndex+Ollama, async lib usage, streaming).
- `docs/` + `mkdocs.yml` (**new**) — docs site config; a `docs/COOKBOOK.md`; API reference via mkdocstrings.
- `.github/workflows/docs.yml` — **new**: build + publish docs (GitHub Pages).
- `py.typed` marker — ship types (add to package data if missing).

## Tasks

### A. Async core
1. Add native async methods: `alookup`, `astore`, `aget_or_call`, `aget_or_call_messages`. Reuse the sync
   core for CPU work; make IO (storage, upstream) awaitable where backends support it (Redis async client
   behind `[async]`; sqlite via thread executor).
2. Ensure thread/async safety with the striped locks from spec 02.
3. Async decorator: `cached_llm_call` detects coroutine functions and returns an async wrapper.

### B. LangChain integration
4. `integrations/langchain/cache.py`: implement LangChain's `BaseCache` interface backed by InferCache
   (exact + semantic), so `set_llm_cache(InferCacheLLMCache(...))` "just works".
5. `integrations/langchain/chat.py`: a thin wrapper/callback that also captures provider usage for
   accounting (spec 04). Provide both `lookup/update` cache and a wrapping runnable.
6. Example: `examples/langchain_ollama_example.py` (miss→hit, paraphrase hit, stats).

### C. LlamaIndex integration
7. `integrations/llamaindex/wrapper.py`: wrap LlamaIndex LLM/embedding calls with InferCache; document
   how to plug into a query engine.
8. Example: `examples/llamaindex_ollama_example.py`.

### D. Typed, discoverable surface
9. Ensure `py.typed` ships and public classes are fully typed (coordinate with spec 07 mypy).
10. Add docstrings with examples to all public API (`InferCache`, `CacheConfig`, adapters, decorator).

### E. Docs site & cookbook
11. `mkdocs.yml` (Material theme + mkdocstrings) rendering existing `docs/*.md` + auto API reference.
12. `docs/COOKBOOK.md`: recipes — OpenAI SDK via gateway, LangChain, LlamaIndex, async app, multi-tenant,
    invalidation, "don't cache live reviews", observability/OTel, Bedrock (link `TESTING_BEDROCK.md`).
13. `.github/workflows/docs.yml`: build on push to main, deploy to GitHub Pages. Link from README.

### F. Quickstart polish
14. A 60-second quickstart in README that produces a real cache hit with Ollama in ≤ 5 lines using the decorator.
15. `infercache doctor` CLI command: checks Python version, optional extras present, Ollama/gateway
    reachability, cache path writability — prints actionable diagnostics.

## Acceptance criteria
- [ ] Async API (`alookup/astore/aget_or_call*`) works and is tested; async decorator supports coroutines.
- [ ] LangChain `BaseCache` integration works with a runnable example (mock-tested; live example documented).
- [ ] LlamaIndex integration works with a runnable example (mock-tested).
- [ ] `py.typed` ships; public API fully typed and docstringed.
- [ ] `mkdocs` site builds and publishes; `docs/COOKBOOK.md` covers the key recipes.
- [ ] `infercache doctor` diagnoses common setup issues.
- [ ] README quickstart yields a cache hit in ≤ 5 lines.

## Test plan
- Async: `aget_or_call` miss→hit with an async fake LLM; assert no event-loop blocking (no sync sqlite in the loop thread).
- LangChain: use the integration with a fake LLM; assert second identical call is served from cache and usage recorded.
- LlamaIndex: analogous mock test.
- Docs: `mkdocs build --strict` passes in CI (no broken refs).
- `infercache doctor`: simulate missing extra / unwritable path; assert clear diagnostics + non-zero exit.

## Checklist
- [ ] Async core + decorator  - [ ] LangChain  - [ ] LlamaIndex  - [ ] Typed + docstrings
- [ ] mkdocs site + COOKBOOK  - [ ] doctor + quickstart
