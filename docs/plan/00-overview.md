# InferCache Execution Plan — Overview & Conventions

This folder is the **agent-executable** breakdown of [`ROADMAP.md`](../../ROADMAP.md).
Each numbered spec is self-contained: **context → problem → files → tasks → acceptance criteria → tests**.
An implementing agent should be able to open one spec and complete it end to end without extra context.

## Reading order (by phase / leverage)

| Order | Spec | Phase |
|-------|------|-------|
| 1 | [`07-quality-and-ci.md`](07-quality-and-ci.md) | 0 — foundation (do first) |
| 2 | [`01-correctness-and-safety.md`](01-correctness-and-safety.md) | 1 — the moat |
| 3 | [`02-performance-and-scale.md`](02-performance-and-scale.md) | 2 |
| 4 | [`03-provider-coverage.md`](03-provider-coverage.md) | 3 |
| 5 | [`04-observability.md`](04-observability.md) | 4 |
| 6 | [`05-security.md`](05-security.md) | 5 |
| 7 | [`06-developer-experience.md`](06-developer-experience.md) | 6 |

## Repository facts an implementer must know

- **Package root:** `src/infercache/` (src layout; `pythonpath = ["src"]` in `pyproject.toml`).
- **Public API:** `from infercache import InferCache, CacheConfig, cached_llm_call, configure, ModelCascade, CascadeStage`.
- **Core wiring:** `core/engine.py` (`InferCache`) composes `core/lookup.py`, `core/store.py`,
  `core/keys.py`, `core/adaptive.py`, `embeddings/*`, `index/vector.py`, `optimization/*`,
  `storage/*`, `metrics/*`.
- **Config:** single dataclass `config/settings.py::CacheConfig` (add new knobs here, with defaults + `validate()`).
- **Storage contract:** `storage/base.py::StorageBackend` (`get/set/delete/list_entries/clear/count`).
- **Entry record:** `storage/models.py::CacheEntry` (prompt, response, embedding, metadata, hits, created_at, adaptive_threshold).
- **Backends:** `memory` (LRU+TTL), `sqlite` (default, WAL, RLock), `redis`.
- **Surfaces:** `gateway/server.py`, `mcp/server.py`, `cli/main.py`, `integrations/wrapper.py` (decorator), `integrations/adapters/*`.
- **Compat shims already exist** (`cache.py`, `adapters.py`, `optimizer.py`, `tokens.py`, `wrapper.py`) — preserve them.
- **Legacy Python:** `requires-python = ">=3.9"`. Keep 3.9 compatibility (no `match`, no PEP 604 in runtime-eval positions unless `from __future__ import annotations` is present — it already is in most modules).

## Global conventions

### Definition of Done (every spec)
A spec is done only when **all** are true:
1. Code implemented behind the existing config/deprecation patterns.
2. New/changed behavior covered by tests; overall line coverage stays **≥ 85%**.
3. `ruff check`, `ruff format --check`, and `mypy` (per the scope in spec 07) pass.
4. `pip-audit`/Bandit clean (no new high/critical).
5. Docs updated: relevant file in `docs/` + the status table in `ROADMAP.md` + the spec's own checklist.
6. No secrets/keys committed; no network calls in unit tests (mock all IO).
7. Backward compatible, or shipped with a deprecation shim + `DeprecationWarning`.

### Branch / PR strategy
- One spec ≈ one PR (or a small stack of ≤3 PRs). Keep PRs < ~600 lines of diff where possible.
- Branch names: `feat/<spec-number>-<slug>` (e.g. `feat/01-confidence-gate`).
- PR description must link the spec and check off its acceptance criteria.
- Every PR runs the full Phase-0 gate (see spec 07). Do not merge on red.

### Coding standards
- Type-hint all new public functions. `from __future__ import annotations` at top of new modules.
- No new **required** third-party dependency in core paths. Heavy deps (faiss, hnswlib, transformers,
  numpy, provider SDKs, otel) go behind **optional extras** and lazy imports with a clear
  `ImportError` message (follow `embeddings/sentence.py` and adapter patterns).
- Public config changes go through `CacheConfig` with a default that preserves current behavior.
- Keep stdlib-only defaults working offline.

### Testing standards
- Unit tests mock all network/subprocess/boto3/urlopen IO. No live provider calls in CI.
- Mark slow/integration tests with `@pytest.mark.integration` (registered in `pyproject.toml`);
  they are opt-in locally and excluded from the default CI unit job.
- Determinism: seed any randomness; freeze time where TTL is involved.
- Add regression tests for every bug fixed (especially cache correctness).

### Performance standards
- Any hot-path change ships with a benchmark number (use `infercache benchmark` and/or the
  microbench added in spec 02). No change may regress p99 lookup latency > 10% without justification.

## Cross-cutting design decisions (decide once, reuse)

1. **Confidence score** is a float in `[0,1]` attached to every lookup result (`result["confidence"]`).
   Semantic hits below `CacheConfig.min_confidence` become misses. Defined in spec 01.
2. **Invalidation** is first-class: entries carry optional `tags: list[str]`; storage gains
   `delete_by_tag`, `delete`, and `touch`. Vector index must stay consistent. Defined in spec 01.
3. **Unified message schema** (`core/schema.py`) is the internal representation all adapters and the
   gateway convert to/from. Defined in spec 03. Introduce it early; migrate adapters incrementally.
4. **Metrics event bus**: a single `metrics.record_event(Event)` sink so OTel/time-series can attach
   without touching call sites. Defined in spec 04.
5. **Policy hooks**: `should_cache(request, response) -> bool` and `redact(text) -> text` callables on
   `CacheConfig` (default no-ops). Enables security/PII and "don't cache live reviews" behavior. Spec 05.

## What NOT to do
- Do not turn InferCache into a multi-model "consensus" product; that is a separate bet (see roadmap §1 rationale).
- Do not add always-on cloud dependencies or telemetry.
- Do not cache live code/security/design reviews by default (respect `.cursor/rules/infercache.mdc`);
  the `should_cache` hook + docs must make this the documented default guidance.
- Do not break the tested paths (Ollama adapter, Cursor MCP, gateway→Ollama, FastAPI→Ollama).
