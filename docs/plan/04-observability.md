# Spec 04 — Observability (Phase 4, prove the value)

> **Goal:** Make savings and behavior provable and debuggable: provider-accurate token/cost accounting,
> time-series metrics, OpenTelemetry traces/metrics, and a live dashboard.

**Metrics moved:** token/cost accounting error **< 5%** when provider usage is available; every
hit/miss explainable; per-model/per-day breakdowns; optional OTel export.

## Context (current behavior)
- `metrics/collector.py` tracks aggregate counters; token counts come from `optimization/tokens.py`
  **heuristics** (`chars/4 + words*0.75`), not provider-reported usage.
- `estimated_cost_reduction_pct` is a rough formula; `benchmark/pricing.py` has static per-model prices.
- No time-series, no per-model/day breakdown, no tracing, no export.
- Gateway exposes `GET /stats` (aggregate JSON only).

## Problem
Users can't fully trust or debug the savings. There's no way to see trends, attribute savings per
model, or trace why a specific request hit/missed.

## Files to touch
- `metrics/events.py` — **new** event model + sink interface.
- `metrics/collector.py`, `metrics/persistent.py` — emit events; keep aggregate compatibility.
- `metrics/timeseries.py` — **new** rolling per-model/per-day counters (SQLite table).
- `metrics/otel.py` — **new** optional OpenTelemetry exporter (extra `[otel]`).
- `optimization/tokens.py` + adapters/gateway — capture **provider-reported** usage when present.
- `benchmark/pricing.py` — externalize prices to `pricing.json`; allow overrides; add "last updated".
- `gateway/server.py` — richer `/stats` (time-series, per-model), `/stats/prometheus` endpoint.
- `cli/main.py` — `infercache stats --json/--since/--by-model`.
- Dashboard: `examples/dashboard.canvas.tsx` or a small static HTML served by the gateway (`/dashboard`).
- Docs: `docs/OBSERVABILITY.md` (**new**).

## Tasks

### A. Event bus (single sink for everything)
1. Define `metrics/events.py::Event` (type: hit/miss/reject/store/evict/error; fields: model, cache_type,
   confidence, tokens_in/out, provider_usage?, latency_ms, user?, ts). Add `record_event(event)` to the
   metrics collector; refactor existing `record_hit/miss/...` to emit events internally (keep public API).
2. Sinks are pluggable: in-memory aggregate (default), persistent, time-series, OTel. Adding a sink must
   not touch call sites.

### B. Provider-accurate accounting
3. When a provider returns usage (OpenAI `usage`, Anthropic `usage`, Bedrock, Gemini), capture
   `prompt_tokens`/`completion_tokens` on the miss and store them on the `CacheEntry`.
4. On a hit, credit **saved tokens** using the stored provider usage (fall back to the estimator only
   when real usage is unavailable). Report an `accounting_source: provider|estimate` field.
5. Move pricing to `benchmark/pricing.json` (input/output $/1M + `last_updated` + `source`); let
   `CacheConfig`/CLI override. Compute cost saved from real usage × price.

### C. Time-series & breakdowns
6. `metrics/timeseries.py`: append-only rolling counters keyed by `(day, model)` in SQLite; expose
   `series(since, by="model")`. Cheap to write (batched with spec 02).
7. CLI: `infercache stats --by-model`, `--since 7d`, `--json`. Gateway `/stats` gains `series` + per-model.

### D. Tracing / metrics export
8. `metrics/otel.py` (extra `[otel]`): optional spans around lookup/store/upstream calls and OTel
   counters/histograms (hit_rate, lookup_latency, tokens_saved). No-op if OTel not installed/enabled.
9. Gateway `/stats/prometheus` exposition endpoint (text format) for scrape-based setups.

### E. Dashboard
10. Ship a lightweight dashboard: hit-rate over time, tokens/$ saved, top cached prompts, per-model
    breakdown, recent misses with reasons/confidence. Either a static page served at gateway `/dashboard`
    or a Cursor canvas example (`examples/dashboard.canvas.tsx`) reading `/stats`.
11. `docs/OBSERVABILITY.md`: how accounting works, how to enable OTel/Prometheus, how to read the dashboard.

## Acceptance criteria
- [ ] A single `record_event` path feeds aggregate, persistent, time-series, and (optional) OTel sinks.
- [ ] Provider-reported usage is captured on miss and used to credit savings on hit (`accounting_source` reported).
- [ ] Token/cost accounting error < 5% vs provider usage on a mocked provider-usage test.
- [ ] Time-series + per-model breakdown available via CLI and gateway `/stats`.
- [ ] Optional OTel export and Prometheus endpoint work behind the `[otel]` extra (no-op when disabled).
- [ ] A dashboard renders hit-rate, savings, and recent misses.
- [ ] `docs/OBSERVABILITY.md` published.

## Test plan
- Feed synthetic events; assert aggregate == time-series rollup == sum of per-model.
- Mock an OpenAI response with `usage`; assert saved tokens on the subsequent hit match provider usage, not the estimator.
- OTel: with a test exporter, assert spans/counters emitted; with extra absent, assert no import error and no-op.

## Checklist
- [ ] Event bus  - [ ] Provider accounting + pricing.json  - [ ] Time-series + CLI/gateway
- [ ] OTel + Prometheus  - [ ] Dashboard  - [ ] OBSERVABILITY.md
