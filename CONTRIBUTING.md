# Contributing

This is currently a single-maintainer portfolio project. This file documents the lightweight
process that's already followed, in case that changes.

## Before you start

Read [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md) and the medical disclaimer in
[README.md](README.md) first. Any contribution that weakens a disclaimer, removes a
synthetic-data label, or adds clinical-sounding language will be rejected regardless of its
technical merit — scientific-integrity framing is a hard constraint of this project, not a
style preference.

## Workflow

1. Branch from `main`, open a PR.
2. CI must pass: `test` (backend), `ml` (ML pipeline), `frontend`, and `security`
   (`pip-audit`/`npm audit`/`detect-secrets` — see [docs/SECURITY_AUDIT.md](docs/SECURITY_AUDIT.md)).
3. Run the relevant local gate before pushing:
   - Backend: `python scripts/check.py` (ruff format/check, mypy, pytest with coverage).
   - Frontend: `npm run check` in `frontend/` (typecheck, lint, format check, test).
4. If you touch the backend OpenAPI schema, regenerate frontend types:
   `npm run api:generate` in `frontend/`, and commit the resulting `openapi.json`/
   `schema.d.ts` diff.

## Code conventions

- Backend: typed SQLAlchemy 2.0 (`Mapped`/`mapped_column`), repository/service layering
  (no raw queries in endpoint functions) — see
  [docs/decisions/ADR-001-backend-architecture.md](docs/decisions/ADR-001-backend-architecture.md).
  Two dependency tiers are enforced by `tests/inference/test_import_isolation.py`: the live
  API (`requirements.txt`) must never import numpy/torch/sklearn/pandas.
- Database changes go through Alembic (`alembic revision --autogenerate`, then review the
  generated file by hand) — never `Base.metadata.create_all()`. See
  [docs/DATABASE_RELEASE_AND_ROLLBACK.md](docs/DATABASE_RELEASE_AND_ROLLBACK.md) before
  writing a migration that drops or alters an existing column.
- Frontend: TypeScript types for API calls are generated (`npm run api:generate`), never
  hand-written against the live schema.
- Tests run against a real PostgreSQL test database (never SQLite, never fully mocked) for
  integration tests; ML tests run against synthetic, generated data only — no real dataset
  download in CI.

## Security-sensitive changes

Any change to authentication, authorization (`CurrentUserDep`/`CurrentSuperuserDep`), rate
limiting, or upload validation should reference (and, if the threat model changes, update)
[docs/THREAT_MODEL.md](docs/THREAT_MODEL.md). Add a test proving the new behavior — see
`tests/integration/test_research_authorization.py` for the pattern used for the Phase 8
admin-only endpoints (deny-by-default test + allow test + unauthenticated test).

## Reporting a security issue

See [SECURITY.md](SECURITY.md) — do not open a public issue for a vulnerability.
