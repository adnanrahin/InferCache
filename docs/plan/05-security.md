# Spec 05 — Security & Multi-Tenant (Phase 5, enterprise-ready)

> **Goal:** Make it safe to run InferCache beyond a single trusted machine: authenticated gateway/MCP,
> optional at-rest encryption, PII redaction hooks, and per-tenant isolation with quotas — without
> breaking the local-first, zero-config default.

**Metrics moved:** no unauthenticated privileged endpoints when auth is enabled; secrets never logged
or committed; opt-in encryption + redaction; tenant isolation enforced.

## Context (current behavior)
- Gateway binds `127.0.0.1` but has **no authentication**; `POST /cache/clear` is unauthenticated, and it
  forwards client-supplied provider API keys upstream.
- MCP trusts whoever spawns the process; no per-user/params scoping in tools.
- Storage keeps **plaintext** prompts/responses (SQLite/Redis). No encryption at rest.
- No PII redaction; no secret scanning in CI (added in spec 07).
- Redis has no auth/TLS guidance; gateway error responses may echo upstream bodies.

## Problem
Any shared or networked deployment leaks credentials and data, and lets anyone read/wipe the cache.
Enterprises cannot adopt without auth, isolation, and data-handling controls.

## Files to touch
- `gateway/server.py` — auth middleware, protected admin routes, safe error bodies, bind/TLS guidance.
- `mcp/server.py` — optional token gate; per-user/params scoping in tools.
- `config/settings.py` — security knobs (auth tokens, encryption, redaction hook, tenant options).
- `security/` — **new** package: `auth.py`, `crypto.py` (at-rest encryption), `redaction.py`.
- `storage/sqlite.py`, `storage/redis.py` — optional transparent encrypt/decrypt of prompt/response fields.
- `core/store.py`, `core/lookup.py` — apply redaction hook before store; tenant scoping in keys.
- Docs: `docs/SECURITY.md` (**new**), `docs/PRIVACY.md` (update), Redis hardening notes.

## Tasks

### A. Gateway authentication & hardening
1. Add `CacheConfig`/`GatewayConfig` auth: `require_auth: bool` + `api_keys: set[str]` (or file/env).
   Enforce a `Authorization: Bearer <key>` (or `X-InferCache-Key`) on all endpoints when enabled.
2. Protect admin routes (`/cache/clear`, `/cache/invalidate`, `/stats` if configured) behind auth even
   when general caching is open; return 401/403 appropriately.
3. Never echo upstream response bodies in error payloads; log to stderr only, with secrets scrubbed.
4. Document safe deployment: bind address, TLS termination (reverse proxy), and that client-forwarded
   provider keys are **not** stored (assert in a test that keys never reach storage).
5. Add optional rate limiting per API key/IP (token bucket) to protect upstreams.

### B. MCP auth & scoping
6. Optional token gate for MCP (env `INFERCACHE_MCP_TOKEN`); if set, require it in `initialize`.
7. Add `user` and `params` scoping to MCP tools so multi-agent setups don't cross-contaminate.

### C. At-rest encryption (opt-in)
8. `security/crypto.py`: authenticated encryption (AES-GCM via `cryptography`, extra `[crypto]`) with a
   key from `CacheConfig.encryption_key` or `INFERCACHE_ENCRYPTION_KEY`. Encrypt `prompt`/`response`
   (and metadata if configured) transparently in sqlite/redis; embeddings/keys stay usable.
9. Key rotation: support a key id prefix so rotated keys can decrypt old entries; document rotation.
10. When encryption is on, ensure semantic lookup still works (embeddings are computed pre-encryption and
    stored separately; do not encrypt the vector unless configured).

### D. PII redaction hook
11. `security/redaction.py`: default regex redactors (emails, phone numbers, API keys, credit cards) and
    a pluggable `CacheConfig.redact: Callable[[str], str]`. Apply before embedding/storing so PII never
    lands in the cache; keep a reversible option off by default.
12. Wire `should_cache` (from spec 01) + redaction into store path; document the "don't cache live
    reviews / secrets" default and how to enforce it.

### E. Multi-tenant isolation & quotas
13. First-class `tenant` scope: fold `tenant` into cache keys and scope filters (library, gateway header
    `X-InferCache-Tenant`, MCP). Ensure cross-tenant lookups can never hit.
14. Per-tenant quotas: max entries / max bytes / TTL overrides; enforce on store with clear errors.
15. Admin: `invalidate(tenant=…)` and stats broken down by tenant (coordinate with spec 04).

### F. Docs & hardening
16. `docs/SECURITY.md`: threat model, auth setup, encryption, redaction, tenant isolation, Redis TLS/auth,
    responsible disclosure. Update `docs/PRIVACY.md` to reflect new options.

## Acceptance criteria
- [ ] With `require_auth=True`, all gateway endpoints reject unauthenticated requests; admin routes always protected.
- [ ] Test proves client-forwarded provider API keys are never written to storage or logs.
- [ ] Optional MCP token gate works; MCP tools support `user`/`params`/`tenant` scoping.
- [ ] At-rest encryption (opt-in) encrypts prompt/response transparently; lookups still work; rotation documented.
- [ ] Redaction hook + defaults strip PII before storage (tested); `should_cache` prevents caching flagged content.
- [ ] Tenant scoping guarantees no cross-tenant hits (tested); per-tenant quotas enforced.
- [ ] `docs/SECURITY.md` published; `PRIVACY.md` updated; no secrets in code/logs (CI secret scan green).

## Test plan
- Auth: requests without/with bad/with good key → 401/403/200; `/cache/clear` always requires auth.
- Key-leak: run a gateway miss with a fake upstream; assert the forwarded `authorization` value is not in storage or any log capture.
- Encryption: store with encryption on; inspect raw sqlite/redis value is ciphertext; lookup returns plaintext; rotate key and still decrypt old entries.
- Redaction: store a prompt containing an email + fake API key; assert stored prompt is redacted and no PII in embeddings text projection.
- Tenant: store under tenant A, lookup under tenant B → miss; quota exceeded → clear error.

## Checklist
- [ ] Gateway auth + hardening + rate limit  - [ ] MCP auth + scoping  - [ ] At-rest encryption
- [ ] Redaction + should_cache  - [ ] Tenant isolation + quotas  - [ ] SECURITY.md/PRIVACY.md
