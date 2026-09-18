# Spec 07 — Quality Foundation & CI (Phase 0, do first)

> **Goal:** Build the safety net that makes every later refactor safe. Enforce lint, types,
> coverage, security, and benchmark-regression gates in CI, and close the biggest test holes.

**Metrics moved:** test coverage → **≥ 85% enforced**; CI gates → pytest + ruff + mypy + coverage + security + benchmark; regressions caught automatically.

## Context
- CI today (`.github/workflows/build-wheel.yml`) runs **pytest only** on 3.10–3.12, then builds/releases wheels.
- `ruff` and `pytest-cov` are dev deps but **never run in CI**. No mypy, no security scan, no coverage gate.
- ~22 modules have no meaningful tests: `integrations/adapters/{openai,anthropic,generic}.py`,
  `storage/redis.py`, `embeddings/{hash,sentence,factory}.py`, `cli/main.py`, `integrations/wrapper.py`,
  and legacy shims `tokens.py`/`optimizer.py`/`adapters.py`/`wrapper.py`.
- `requires-python = ">=3.9"` but 3.9 is not in the CI matrix.

## Problem
Without static analysis, coverage gates, and security scanning, correctness/perf refactors in later
phases are high-risk. Untested adapters and Redis mean provider work is flying blind.

## Files to touch
- `pyproject.toml` — ruff rule set, mypy config, coverage config, pytest markers.
- `.github/workflows/ci.yml` — **new** dedicated CI (split from release workflow) with parallel gate jobs.
- `.github/workflows/build-wheel.yml` — keep release logic; make it depend on the new CI passing.
- `.github/dependabot.yml` — **new** (pip + github-actions weekly).
- `tests/integrations/test_openai.py`, `tests/integrations/test_anthropic.py`,
  `tests/integrations/test_generic.py`, `tests/integrations/test_wrapper.py` — **new**.
- `tests/storage/test_redis.py` — **new** (use `fakeredis` dev dep, or a hand mock).
- `tests/embeddings/test_backends.py` — **new** (hash, factory, tfidf edge cases; sentence behind `@pytest.mark.integration`).
- `tests/cli/test_cli.py` — **new** (invoke `infercache.cli.main.main([...])` for store/lookup/stats/clear).
- `tests/conftest.py` — register markers, shared fixtures.
- `CONTRIBUTING.md` — **new** (how to run gates locally).

## Tasks
1. **Ruff gate.** In `pyproject.toml` enable a real rule set:
   `select = ["E","F","I","UP","B","SIM","C4","PTH","RUF"]`, keep `line-length = 100`. Fix violations or
   add narrowly-scoped `# noqa` with reason. Add `ruff format` and check it in CI.
2. **Mypy gate.** Add `mypy` to `dev` extra. Configure:
   - Global: `python_version = 3.9`, `warn_unused_ignores`, `no_implicit_optional`.
   - **Strict** on `src/infercache/core/`, `config/`, `storage/`, `metrics/` (`disallow_untyped_defs`).
   - Looser (non-strict) elsewhere initially; tighten over time. Third-party without stubs → `ignore_missing_imports`.
3. **Coverage gate.** Add `[tool.coverage.run] source = ["infercache"]` and
   `[tool.coverage.report] fail_under = 85`. CI runs `pytest --cov=infercache --cov-report=xml --cov-report=term-missing`.
4. **Security gate.** Add `pip-audit` and `bandit` to CI (bandit scoped to `src/`). Fail on high/critical.
   Add a `gitleaks` (or `trufflehog`) job to catch committed secrets.
5. **Pytest markers.** Register `integration` and `slow` markers; default CI unit job runs
   `-m "not integration and not slow"`. Add a separate optional `integration` job (manual/nightly).
6. **Python matrix.** Add **3.9** to the matrix (or explicitly drop 3.9 support in `pyproject.toml`
   and README — pick one; document the decision).
7. **Benchmark regression job.** New CI job runs `infercache benchmark --queries 300 --repeat-rate 0.4`
   and the spec-02 microbench, writes JSON, and compares hit-rate/latency against a committed baseline
   in `benchmarks/baseline.json` with a tolerance (fail if hit-rate drops > 3 pts or p99 latency worsens > 20%).
8. **Close test holes.** Write the new test files above. Target the untested modules first.
   Use mocking patterns already in `tests/integrations/test_ollama.py` and `tests/gateway/test_gateway.py`.
9. **Pre-commit (optional but recommended).** Add `.pre-commit-config.yaml` running ruff + ruff-format + a
   secrets check, and document it in `CONTRIBUTING.md`.
10. **CONTRIBUTING.md.** Document: `pip install -e ".[dev]"`, `ruff check`, `ruff format`, `mypy src`,
    `pytest --cov`, how to run integration tests, and the Definition of Done.

## Acceptance criteria
- [ ] CI has parallel jobs: `lint` (ruff), `types` (mypy), `test` (pytest+coverage, 3.9–3.12), `security` (pip-audit+bandit+secrets), `benchmark`.
- [ ] `fail_under = 85` enforced and currently passing.
- [ ] Release workflow only runs after the CI workflow passes.
- [ ] New tests exist for OpenAI/Anthropic/Generic adapters, Redis storage, embeddings factory/hash, CLI, decorator.
- [ ] Dependabot configured; secrets scan runs on every PR.
- [ ] `CONTRIBUTING.md` documents the full local gate.
- [ ] Baseline benchmark committed; regression job wired.

## Test plan
- Verify each new adapter test asserts miss→store→hit and that `**kwargs` are forwarded to the provider mock.
- Redis test uses `fakeredis` (add to `dev`), covers set/get/delete/list/ttl and `create_storage(backend="redis")`.
- CLI test invokes `main(["store", ...])`, `main(["lookup", ...])`, asserts exit code 0 and JSON output.
- Confirm `-m "not integration"` excludes the sentence-transformers test in the default job.

## Checklist (update as you land work)
- [ ] Ruff gate  - [ ] Mypy gate  - [ ] Coverage gate  - [ ] Security gate
- [ ] Markers + matrix  - [ ] Benchmark regression  - [ ] Test holes closed  - [ ] CONTRIBUTING.md
