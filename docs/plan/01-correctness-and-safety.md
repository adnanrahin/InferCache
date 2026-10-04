# Spec 01 — Correctness & Safety (Phase 1, the moat)

> **Goal:** Make every semantic hit *defensible*. Add calibrated confidence, persistent adaptive
> learning, first-class invalidation, and a labeled evaluation harness that publishes a
> false-positive rate. This is the single biggest differentiator vs every other LLM cache.

**Metrics moved:** semantic **false-positive rate < 1%** at reported hit-rate; adaptive learning
survives restarts; wrong entries can be invalidated in O(1); regressions caught by an eval set.

## Context (current behavior)
- `core/lookup.py` accepts a semantic hit when `best_score ≥ threshold` AND
  (`best - second ≥ semantic_score_margin` OR single candidate). Threshold comes from
  `CacheConfig.similarity_threshold`, optionally adjusted live by `core/adaptive.py`.
- `core/adaptive.py` keeps per-bucket `{hits, errors}` **in memory only** — lost on restart, coarse
  16-dim bucketing, and the `adaptive_threshold` stored on each `CacheEntry` is never used at lookup.
- There is **no per-entry invalidation** beyond full `clear()`; TTL eviction in SQLite does **not**
  update the in-memory vector index → stale index entries can be returned.
- Scope matching (`_in_scope`) is exact metadata equality only.
- `cache_feedback` tunes thresholds but cannot delete a bad entry.

## Problem
Semantic caches fail dangerously when they return a confident-looking wrong answer. Today we have no
single confidence number, no way to learn safely across restarts, no way to surgically remove a bad
entry, and no measurement of how often we're wrong.

## Files to touch
- `config/settings.py` — new knobs (below) + `validate()`.
- `core/lookup.py` — compute + return `confidence`; enforce `min_confidence`; consult persisted adaptive state.
- `core/adaptive.py` — persist stats; finer bucketing; expose calibration.
- `core/store.py`, `storage/models.py` — add `tags` to `CacheEntry`; write `last_accessed`.
- `storage/base.py` + `memory.py` + `sqlite.py` + `redis.py` — add `delete_by_tag`, `touch`, and ensure
  deletes/evictions are observable so the index can stay consistent.
- `core/engine.py` — new public methods: `invalidate(prompt=…, key=…, tag=…)`, keep index in sync on
  eviction/delete; wire confidence into `get_or_call*` results.
- `index/vector.py` — call `remove()` on eviction/delete/overwrite; add a consistency check.
- `mcp/server.py` — new tool `cache_invalidate`; include `confidence` in `cache_lookup` output.
- `gateway/server.py` — surface `confidence` in the `infercache` response block; honor `min_confidence`.
- `eval/` — **new** package: labeled dataset + runner (below).
- Docs: `docs/SAFETY.md` (**new**), update `docs/MCP.md`, `README.md`.

## Tasks

### A. Calibrated confidence
1. Add `CacheConfig.min_confidence: float = 0.0` (default off to preserve behavior; recommended 0.8 in docs).
2. In `core/lookup.py`, compute `confidence` for a semantic candidate from a blend of:
   - primary similarity (embedding cosine or `text_similarity`),
   - the **margin** to the runner-up (bigger margin → higher confidence),
   - the adaptive bucket's historical accuracy (from persisted stats).
   Normalize to `[0,1]`. Document the formula in `docs/SAFETY.md`.
3. Attach `confidence` and `cache_type` to every lookup/`get_or_call*`/gateway/MCP result.
4. If `cache_type == "semantic"` and `confidence < min_confidence` → treat as **miss** and record a
   `threshold_reject` metric.

### B. Persistent, better adaptive thresholds
5. Persist adaptive stats next to the cache: for sqlite backend, a small `adaptive_stats` table in the
   same DB; otherwise a JSON sidecar (mirror the TF-IDF `state_path` pattern). Load on init, save on update (batched — see spec 02).
6. Improve bucketing: use a locality-sensitive signature (e.g. sign bits of a random-projection of the
   embedding, k≈16 bits) instead of rounding raw dims. Keep it dependency-free.
7. Actually **use** the persisted per-bucket accuracy in both the threshold and the confidence score.
8. Extend `feedback(prompt, was_correct)` to also accept an explicit `key` and to optionally
   **invalidate** the entry when `was_correct=False` and `CacheConfig.invalidate_on_negative_feedback=True` (new, default False).

### C. First-class invalidation
9. Add `tags: list[str]` to `CacheEntry` (default empty) and allow `store(..., tags=[...])`.
10. Storage: implement `delete(key)`, `delete_by_tag(tag)`, `touch(key)` on all backends
    (memory, sqlite, redis). Redis: maintain a `tag → set(keys)` index to avoid `KEYS` scans.
11. Engine: `invalidate(*, key=None, prompt=None, model="", tag=None)` deletes matching entries from
    **both** storage and the vector index, and updates counters.
12. **Fix index staleness:** whenever an entry is deleted or evicted (including SQLite TTL/LRU
    eviction), call `vector_index.remove(key)`. Add an assertion/consistency test that index size
    tracks storage count.
13. MCP: add `cache_invalidate` tool (`prompt`/`model`/`tag`). Gateway: `POST /cache/invalidate`.

### D. Negative / "again" caching guardrails
14. Add a `should_cache(request, response) -> bool` hook on `CacheConfig` (default: cache non-empty
    responses). Use it to implement the documented default: **do not cache** obviously volatile answers
    (empty, error strings, or when the caller passes `no_store=True`). This is also the hook security/PII uses (spec 05).
15. Support explicit per-call `bypass=True` (force miss + store fresh) and `no_store=True` on
    `get_or_call*`, gateway (`X-InferCache-Bypass` header), and MCP.

### E. Semantic evaluation harness (the proof)
16. Create `eval/` with:
    - `eval/datasets/semantic_pairs.jsonl` — labeled triples `{"a","b","should_hit"}` covering
      true paraphrases (should hit) and hard negatives (look similar, must NOT hit — e.g. "capital of
      France" vs "capital of Germany", "sort ascending" vs "sort descending", negations, unit changes).
      Seed with ≥150 pairs; make it easy to extend.
    - `eval/run_eval.py` — loads the set, runs lookups across embedding backends + thresholds, reports
      precision/recall, **false-positive rate**, and a confusion matrix; writes `eval/report.md`.
17. Add a CI-friendly `pytest` that asserts false-positive rate ≤ a committed budget on the default
    config (mark `slow` if needed).
18. Document results in `docs/SAFETY.md` and link from README.

## Acceptance criteria
- [ ] Every lookup/`get_or_call`/gateway/MCP result includes a `confidence` in `[0,1]`.
- [ ] `min_confidence` demotes low-confidence semantic hits to misses (tested).
- [ ] Adaptive stats persist across process restarts (tested with sqlite + sidecar).
- [ ] `invalidate(key=…/prompt=…/tag=…)` removes from storage **and** vector index; index size stays consistent after eviction (tested).
- [ ] `cache_invalidate` MCP tool and gateway `POST /cache/invalidate` work.
- [ ] `should_cache`, `bypass`, and `no_store` behave as specified across library/gateway/MCP.
- [ ] `eval/run_eval.py` produces `eval/report.md` with a published false-positive rate; CI asserts it stays within budget.
- [ ] `docs/SAFETY.md` explains confidence, invalidation, and the "don't cache live reviews" default.

## Test plan
- Hard-negative tests: store "capital of France?", lookup "capital of Germany?" → **miss** (regression test).
- Confidence monotonicity: paraphrase pairs score higher confidence than unrelated pairs.
- Restart test: record feedback, restart engine, assert thresholds/accuracy persisted.
- Invalidation: store with `tags=["docs"]`, `invalidate(tag="docs")`, assert gone from storage + index + subsequent miss.
- Eviction consistency: fill past `max_cache_entries`, assert index length == storage count.

## Checklist
- [ ] Confidence  - [ ] Persistent adaptive  - [ ] Invalidation API  - [ ] Index consistency
- [ ] should_cache/bypass/no_store  - [ ] Eval harness + report  - [ ] docs/SAFETY.md
