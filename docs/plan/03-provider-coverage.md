# Spec 03 — Provider Coverage & Fidelity (Phase 3, works everywhere)

> **Goal:** One unified internal message schema; first-class adapters for every major provider; and
> full-fidelity caching of **tool calls, multimodal content, logprobs, and streaming** (including
> Anthropic). Sampling params are scoped into the cache key everywhere.

**Metrics moved:** **10+ tested providers**; streaming cache correctness for all; no silent loss of
tool/multimodal content; adapter params scoped like the gateway.

## Context (current behavior)
- Adapters (`integrations/adapters/*`) each hand-convert messages; only **text** is cached. Tool calls,
  images, logprobs, and reasoning tokens are dropped.
- Adapter `**kwargs` (temperature, etc.) go to the provider but are **not** in the cache key — unlike the
  gateway, which fingerprints sampling params (`_params_fingerprint`).
- Gateway caches OpenAI streaming but **forces Anthropic non-streaming**.
- No adapters for Google Gemini, Vertex AI, Azure OpenAI, Cohere, Mistral, Groq.

## Problem
"Best cache for all providers" requires (a) breadth of providers and (b) fidelity — caching the whole
response, not just text — and (c) consistent, correct cache keys regardless of surface.

## Files to touch
- `core/schema.py` — **new** unified request/response model.
- `integrations/adapters/base.py` — convert to/from the schema; scope sampling params into the key.
- `integrations/adapters/{openai,anthropic,bedrock,ollama,llamacpp,generic}.py` — migrate to schema; capture full response.
- `integrations/adapters/{gemini,vertex,azure_openai,cohere,mistral,groq}.py` — **new**.
- `integrations/adapters/__init__.py` + `integrations/__init__.py` — export new adapters (lazy imports).
- `gateway/server.py` — Anthropic streaming; cache tool calls/multimodal; unify key building with schema.
- `pyproject.toml` — new optional extras: `gemini`, `vertex`, `azure`, `cohere`, `mistral`, `groq`.
- Tests under `tests/integrations/` for every adapter (mocked).
- Docs: `docs/PROVIDERS.md` (**new**), update README status table.

## Tasks

### A. Unified schema (do this first; other phases benefit)
1. Define provider-neutral dataclasses in `core/schema.py`:
   - `Message{role, content}` where `content` is a list of typed parts: `TextPart`, `ImagePart`
     (url/base64+mime), `AudioPart`, `ToolCallPart`, `ToolResultPart`.
   - `ChatRequest{model, messages, tools?, sampling: SamplingParams, extra}` and
     `ChatResponse{text, tool_calls?, parts?, finish_reason, usage?, logprobs?, raw}`.
   - `SamplingParams{temperature, top_p, top_k, max_tokens, stop, seed, presence_penalty, frequency_penalty, response_format, reasoning_effort, ...}`.
2. Provide a canonical, order-stable serialization used for cache keys (JSON, sorted) that includes
   messages + tools + sampling. This becomes the one true key builder shared by adapters **and** gateway.
3. Migrate the gateway's `_messages_cache_repr` + `_params_fingerprint` to use the schema key builder
   (keep behavior equivalent; add regression tests).

### B. Full-fidelity response caching
4. Store the full `ChatResponse` (tool calls, parts, finish_reason, usage, logprobs) — not just text.
   Extend `CacheEntry.response` handling to serialize structured responses (JSON) with a version tag.
5. On hit, reconstruct the provider-shaped response (OpenAI/Anthropic/etc.) including tool calls and
   multimodal parts. Add round-trip tests per provider.
6. Keep a text projection for `text_similarity`/embeddings, but never lose structured data.

### C. Sampling-param scoping in adapters
7. In `BaseAdapter`, fold `SamplingParams` into the cache scope (same as gateway) so identical messages
   with different temperature/seed/response_format don't collide. Document which params are keyed.

### D. Streaming everywhere
8. Anthropic streaming in the gateway: on miss, stream upstream SSE live while assembling the full
   response for storage; on hit, replay as Anthropic-style SSE (mirror the OpenAI path).
9. Add a streaming helper to adapters (`chat_stream`) that yields chunks while caching the assembled
   response, so library users get streaming + caching too.

### E. New providers (each: adapter + mocked tests + docs row)
10. **Google Gemini** (`google-generativeai`) — extra `[gemini]`.
11. **Vertex AI** (`google-cloud-aiplatform`) — extra `[vertex]`.
12. **Azure OpenAI** (reuse `openai` SDK with Azure config) — extra `[azure]` (may reuse `[openai]`).
13. **Cohere** (`cohere`) — extra `[cohere]`.
14. **Mistral** (`mistralai`) — extra `[mistral]`.
15. **Groq** (OpenAI-compatible) — extra `[groq]` (can subclass the OpenAI adapter/base URL).
16. Each adapter: lazy import with a clear `ImportError` message; `chat`, `complete`, and (where
    supported) `chat_stream`, `list_models`; converts via `core/schema.py`.

### F. Docs
17. `docs/PROVIDERS.md`: matrix of provider × {chat, stream, tools, multimodal, tested?} with copy-paste
    examples. Update README + GETTING_STARTED status tables.

## Acceptance criteria
- [ ] `core/schema.py` exists and is the single cache-key builder for adapters + gateway (regression-tested equivalence).
- [ ] Tool calls and multimodal parts survive a cache round-trip for OpenAI and Anthropic (tested).
- [ ] Adapter cache keys include sampling params (tested: same messages + different temperature ⇒ different entry).
- [ ] Anthropic streaming works through the gateway (miss streams live + caches; hit replays SSE).
- [ ] Adapters exist and are mock-tested for Gemini, Vertex, Azure OpenAI, Cohere, Mistral, Groq.
- [ ] `docs/PROVIDERS.md` matrix published; README status table updated.

## Test plan
- Schema key equivalence: assert new key builder matches old gateway keys for existing cases.
- Fidelity: mock an OpenAI tool-call response, cache it, assert hit reconstructs identical tool_calls.
- Streaming: mock SSE upstream for Anthropic; assert live pass-through on miss and identical assembled text on hit.
- New adapters: standard miss→store→hit with mocked SDK clients; assert no live network in CI.

## Checklist
- [ ] Unified schema + shared key  - [ ] Full-fidelity responses  - [ ] Param scoping
- [ ] Anthropic + library streaming  - [ ] Gemini/Vertex/Azure/Cohere/Mistral/Groq  - [ ] PROVIDERS.md
