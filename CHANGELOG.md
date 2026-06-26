# Changelog

Phase-by-phase history. Dates are commit dates from `git log`, not calendar estimates.

## Phase 8 — Security hardening and portfolio release (2026-06-26)

- Added per-process rate limiting (`app/core/rate_limit.py`) on login, register, refresh,
  both inference endpoints, and the three research write endpoints.
- Enforced `User.is_superuser` (present since Phase 1, previously unused) on the three
  research write endpoints via a new `CurrentSuperuserDep` — any other authenticated user now
  gets `403` instead of `200`/`201`.
- Added `GET /version` (safe release metadata: app version, environment, optional git
  commit/model version, never fabricated).
- Added `scripts/promote_superuser.py` (the only way to grant administrator status).
- Added `frontend` and `security` (`pip-audit`/`npm audit`/`detect-secrets`) jobs to CI; added
  a workflow-level least-privilege `permissions: contents: read`.
- Added `.secrets.baseline` (audited hashes only, no raw secret values).
- New documentation: `docs/THREAT_MODEL.md`, `docs/SECURITY_AUDIT.md`, `docs/DEPLOYMENT.md`,
  `docs/OPERATIONS_RUNBOOK.md`, `docs/DATABASE_RELEASE_AND_ROLLBACK.md`,
  `docs/DATA_AND_MODEL_PROVENANCE.md`, `docs/KNOWN_LIMITATIONS.md`,
  `docs/PORTFOLIO_CASE_STUDY.md`, plus `CONTRIBUTING.md`, this file, and `CITATION.cff`.
- Rebuilt `README.md` to cover Phases 4-8 (previously stopped at Phase 3).

## Phase 7 — Research evaluation platform (2026-06-26)

- Formal study configuration, dataset quality/leakage audits, evaluation runs with
  NaN-safe metrics and confidence intervals, model/dataset card groundwork, and a new
  `/app/research` frontend section. See `docs/PHASE_7_PROGRESS.md`.

## Phase 6 — Controlled dataset research workflow (2026-06-25)

- Replaced the "upload any image" demo with a controlled flow: dataset registry → sample
  browser → inference on a known sample → ground-truth comparison. New `datasets`/
  `dataset_samples` tables; dev-only idempotent seed scripts.

## Phase 5/4 — Frontend foundation, analyze/result flow, public navigation (2026-06-25)

- Scaffolded the React/TypeScript/Vite app, auth flow, i18n (EN/PL), and the
  analyze→predict→result Grad-CAM rendering flow; fixed public-navigation and i18n issues
  found along the way.

## Phase 3 — Histopathology inference API (2026-06-25)

- Wired a verified Phase 2 model bundle into the Phase 1 API as a real inference endpoint:
  upload validation, preprocessing parity, calibration/decision policy, optional Grad-CAM,
  `model_deployments` audit trail. New bridging package `medrisk_inference/`.

## Phase 2 — Histopathology ML foundation (2026-06-24)

- Standalone, reproducible PyTorch pipeline (`medrisk_ml/`): data, models, training,
  leakage-safe evaluation, calibration, Grad-CAM, file-based model/experiment registry.

## Phase 1 — Backend foundation (2026-06-24)

- FastAPI + PostgreSQL backend: JWT auth with refresh-token rotation, Argon2 password
  hashing, request/error handling, Alembic migrations, tests, CI.
