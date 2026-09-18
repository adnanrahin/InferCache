# Spec 02 — Performance & Scale (Phase 2, hot-path ready)

> **Goal:** Make InferCache fast and safe under concurrent production load: no O(n) scans, a
> persistent incremental ANN index, non-blocking IO, sharded locking, batched metric writes, and a
> lazy, sub-150ms import.

**Metrics moved:** p50 < **1 ms** / p99 < **10 ms** lookup at 100k entries; import < **150 ms**;
no hot-path IO stalls; benchmark regression job stays green.

## Context (current behavior)
- Semantic fallback in `core/lookup.py` does an **O(n) scan** of all entries when the vector index is
  disabled/empty. `_rebuild_index` loads **all** entries at startup.
- `index/vector.py` is **in-memory only**, rebuilt from SQLite on init; FAISS is a flat exact index and
  is **fully rebuilt** on any update/remove.
- All network IO is **blocking `urllib.request.urlopen`** (gateway, Ollama, llama.cpp); no pooling.
- Gateway serializes all lookups/stores behind one global `threading.RLock`.
- `metrics/persistent.py` commits to SQLite on **every** hit/miss (hot-path fsync/lock contention).
- `embeddings/base.py::text_similarity` calls `embed()` **twice** per comparison.
- TF-IDF hashes tokens into 512 dims (collisions) and isn't L2-normalized.

## Problem
The design is fine for demos but has multiple hot-path stalls and O(n) behaviors that will fall over
under real traffic or large caches.

## Files to touch
- `index/vector.py` — persistent, incremental ANN (hnswlib/faiss) + disk snapshot + safe fallback.
- `core/lookup.py` — remove O(n) fallback path (require index or a bounded scan); cache query embedding.
- `core/engine.py` — lazy index load / mmap snapshot; background rebuild option.
- `embeddings/base.py`, `tfidf.py`, `sentence.py` — single-embed `text_similarity`; L2-normalize; batch API.
- `storage/sqlite.py`, `storage/redis.py` — pooled connections; Redis `SCAN` (not `KEYS`); pipelines.
- `metrics/persistent.py` — batched/debounced writes (flush every N events or T seconds, and on close).
- `gateway/server.py` + adapters (`ollama.py`, `llamacpp.py`) — async or pooled non-blocking HTTP; sharded/striped locks.
- `benchmarks/` — **new** microbench + baseline JSON (pairs with spec 07's regression job).
- Docs: `docs/PERFORMANCE.md` (**new**).

## Tasks

### A. Vector index: persistent + incremental
1. Add an optional **hnswlib** backend (extra `[ann]`) with add/remove/search and on-disk save/load;
   keep FAISS and NumPy/pure-Python fallbacks. Selection order: hnswlib → faiss → numpy → python.
2. Persist the index to `~/.infercache/index.bin` (or next to `sqlite_path`); load on init instead of
   full rebuild. Store a small manifest (dim, count, embedding_model) to detect incompatibility and
   trigger a one-time rebuild if the embedding model changed.
3. Make add/remove **incremental** (no full rebuild); for FAISS, batch removes and compact periodically.
4. On dimension mismatch, rebuild rather than silently dropping vectors (coordinate with spec 01 index consistency).

### B. Kill O(n) hot paths
5. When `use_vector_index=True`, never fall back to a full scan; if the index is cold, build lazily in
   the background and serve exact-only until ready (log a one-time warning).
6. If `use_vector_index=False`, cap the scan at a configurable `max_scan_entries` and document the tradeoff.
7. Cache the query embedding once per lookup; pass it to rescoring so we never embed the same text twice.

### C. Embedding speed & quality
8. Refactor `text_similarity` to accept optional precomputed embeddings and never embed twice.
9. L2-normalize TF-IDF output; make dimensions configurable (default up from 512 → 1024) and document
   the collision/latency tradeoff.
10. Add a `embed_batch(texts)` method to the embedding interface; use it in eval/benchmark and
    index rebuilds. MiniLM uses real batching.

### D. Non-blocking IO & concurrency
11. Replace blocking `urlopen` in gateway/adapters with a pooled client (`http.client` keep-alive pool,
    or `httpx` behind an extra). Provide an **async** gateway path (`asyncio`/`aiohttp` optional) while
    keeping the sync server working.
12. Replace the gateway's single global `RLock` with **striped locks** keyed by cache key hash so
    independent keys don't contend. Keep store atomicity per key.
13. Ensure `MemoryStorage` is thread-safe (add a lock) since gateway may use `backend=memory`.

### E. Metrics off the hot path
14. Make `PersistentMetrics` **debounced**: accumulate in memory, flush every `N` events or `T` seconds
    and on shutdown/`atexit`. Guarantee no data loss on clean exit; document at-most-`T` loss on crash.

### F. Import-time budget
15. Audit `__init__.py` imports; lazy-import heavy/optional modules (providers, numpy, faiss, otel).
    Add a test that `import infercache` pulls in no optional heavy deps and stays under a time budget.

### G. Benchmarks
16. Add `benchmarks/microbench.py`: builds N entries, measures p50/p99 for exact + semantic lookup and
    store, and index build time; emits JSON. Commit a `benchmarks/baseline.json`. Wire into spec-07 CI.
17. Write `docs/PERFORMANCE.md` with methodology + latest numbers + tuning guide.

## Acceptance criteria
- [ ] No code path performs a full O(n) storage scan when `use_vector_index=True`.
- [ ] Vector index persists to disk and loads incrementally; changing embedding model triggers a clean rebuild.
- [ ] `text_similarity` embeds at most once; TF-IDF output is L2-normalized; `embed_batch` exists.
- [ ] Gateway/adapters use pooled/non-blocking HTTP; gateway uses striped locks; memory storage is thread-safe.
- [ ] Persistent metrics are batched; no per-event SQLite commit on the hot path.
- [ ] `import infercache` stays under the committed time budget and imports no optional heavy deps.
- [ ] `benchmarks/microbench.py` + baseline committed; CI regression job green.
- [ ] p50 < 1 ms / p99 < 10 ms for warm lookups at 100k entries on CI hardware (record actuals in `docs/PERFORMANCE.md`).

## Test plan
- Concurrency: hammer the gateway with N threads on distinct keys; assert no deadlock and near-linear throughput vs single global lock.
- Index persistence: build index, restart, assert no full rebuild and identical search results.
- Metrics batching: record 10k events, assert commit count ≪ 10k and final persisted totals correct.
- Import budget: `time python -c "import infercache"` under budget; assert `sys.modules` lacks `numpy`, `faiss`, provider SDKs after bare import.

## Checklist
- [ ] Persistent ANN  - [ ] Kill O(n)  - [ ] Embedding speed  - [ ] Non-blocking IO + striped locks
- [ ] Batched metrics  - [ ] Import budget  - [ ] Benchmarks + PERFORMANCE.md
