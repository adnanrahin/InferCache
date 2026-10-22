# Cache correctness, confidence gating, and targeted invalidation

## Problem

Semantic caching had three correctness gaps that limit production trust:

1. **False hits had no brake.** A semantic match above the similarity threshold was
   always served, even when it barely cleared the bar, had a close runner-up, or
   landed in an embedding region with a bad accuracy history.
2. **Cache identity ignored sampling.** `temperature=0` and `temperature=1.2`
   requests shared one entry, so deterministic callers could receive creative-mode
   answers and vice versa.
3. **Stale entries could only be nuked.** The only remedies for a wrong or outdated
   answer were `cache_clear` (loses everything) or waiting out the TTL. Adaptive
   threshold learning was also lost on every restart.

## What changed

### Confidence-gated lookups
- Every lookup result now carries `confidence`: 1.0 for exact hits, 0.0 for misses,
  and for semantic hits a calibrated blend of similarity score, margin over the
  runner-up candidate, and the adaptive per-bucket accuracy history.
- New `min_confidence` setting (default 0.0 = off) demotes low-confidence semantic
  hits to misses and records them as threshold rejects.
- MCP `cache_lookup` and gateway hit responses expose `confidence`, `cache_type`,
  and `payload_kind`.

### Payload-aware optimization
- New `classify_payload()` (stdlib-only) labels prompts prose / JSON / code.
  Structured payloads are never sentence-pruned, so optimization can no longer
  corrupt JSON or code prompts.
- Long system prompts (>= `static_prefix_min_tokens`) are peeled off as a frozen
  prefix before optimization and re-attached byte-identical, keeping them stable
  for provider-side prefix caches.

### Sampling-scoped identity
- `sampling_scope()` extracts temperature / top_p / top_k / seed / max_tokens /
  penalties into the cache key scope. Wired through all six adapters, the gateway,
  and `*_messages` engine calls, so different sampling settings get different entries.

### Targeted invalidation
- `InferCache.invalidate(key=… | prompt=… | tag=…)` deletes entries from storage
  **and** the vector index together and returns the count.
- `store(..., tags=[...])` groups entries for bulk invalidation (tags are metadata,
  not key scope).
- Exposed as MCP tool `cache_invalidate` and gateway `POST /cache/invalidate`.
- `feedback(..., was_correct=False, invalidate=True)` deletes the offending entry
  while still tuning the threshold.
- `get_or_call(..., bypass=True)` forces a fresh upstream call (refreshes the
  entry); `no_store=True` skips persistence for volatile prompts.

### Durability and drift repair
- `AdaptiveThreshold` persists its per-bucket stats to an atomic JSON sidecar
  (`adaptive_state.json` next to the SQLite DB) and reloads on startup; corrupt
  state files are ignored safely.
- The vector index periodically resyncs against storage (every 100 stores) so TTL
  evictions can no longer leave ghost embeddings that shadow real lookups.

## Validation

- `pytest -m "not integration and not slow"`: **77 passed** (14 new tests:
  invalidation by key/prompt/tag/scope, index consistency, adaptive persistence
  round-trip + corrupt-file tolerance, bypass/no_store, MCP invalidate/feedback,
  confidence surfacing).
- `bandit -c pyproject.toml -r src -ll`: clean.
- `mypy --config-file pyproject.toml`: clean (64 files).
- `ruff` could not run locally (binary blocked by local AV); relying on CI lint job.

No new runtime dependencies; all additions are stdlib-only and Python 3.9 compatible.
