# Contributing to InferCache

Thanks for helping build the best LLM cache. Start with [`ROADMAP.md`](ROADMAP.md) and the
execution specs in [`docs/plan/`](docs/plan/). Every change must meet the Definition of Done in
[`docs/plan/00-overview.md`](docs/plan/00-overview.md).

## Setup

```bash
python -m venv .venv && . .venv/Scripts/Activate.ps1   # Windows
# or: python -m venv .venv && source .venv/bin/activate  # macOS/Linux
pip install -e ".[dev]"
```

## Run the quality gates locally (same as CI)

```bash
ruff check src tests            # lint
ruff format --check src tests   # formatting
mypy                            # types (strict on core/, config/, storage/, metrics/)
pytest -q -m "not integration and not slow" --cov=infercache --cov-report=term-missing
bandit -r src -ll               # static security scan
pip-audit                       # dependency vulnerabilities (advisory)
```

Auto-fix what you can:

```bash
ruff check src tests --fix
ruff format src tests
```

## Testing rules

- Unit tests must mock all network / subprocess / boto3 / `urlopen` IO. No live provider calls in CI.
- Mark slow or live tests with `@pytest.mark.integration` or `@pytest.mark.slow`; they are excluded
  from the default suite and run opt-in.
- Add a regression test for every bug fixed — especially cache-correctness bugs.
- Coverage gate: overall line coverage must stay **≥ 85%**.

## Conventions

- Branch names: `feat/<spec-number>-<slug>` (e.g. `feat/01-confidence-gate`).
- One spec ≈ one PR; keep diffs small. Link the spec and check off its acceptance criteria in the PR.
- No new **required** third-party dependency in core paths — heavy deps go behind optional extras
  with lazy imports (see `embeddings/sentence.py` and the provider adapters for the pattern).
- Keep stdlib-only defaults working offline. Preserve the compat shims (`cache.py`, `adapters.py`, …).
- Never commit secrets or API keys. The secret-scan CI job will fail the build.

## Security

Report vulnerabilities privately (see `docs/SECURITY.md` once Phase 5 lands). Do not open public
issues for security problems.
