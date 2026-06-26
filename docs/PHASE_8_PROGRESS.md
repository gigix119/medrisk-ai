# Phase 8 progress — Production readiness, security hardening, portfolio release

## Audit snapshot

- **Audit date:** 2026-06-26
- **Branch:** `main`
- **Commit at start:** `88c2b36` ("feat: add research evaluation platform")
- **Working tree:** clean
- **Backend:** FastAPI + SQLAlchemy 2.0 async + asyncpg + Alembic + Pydantic v2, Python 3.12 (pinned in all Dockerfiles, `pyproject.toml` allows `>=3.11,<3.13`)
- **Frontend:** React 19 + TypeScript 5.9 + Vite, i18n (EN/PL)
- **Database:** PostgreSQL 16, Alembic-only migrations (no runtime `create_all`)
- **Auth:** JWT (HS256) access (15 min) + refresh (7 days, single-use rotation), Argon2 password hashing
- **Deployment:** none exists yet — no Procfile/fly.toml/render.yaml/k8s/terraform; CI has no deploy job; no live URL anywhere in the repo

## Phase 7 release gate — VERIFIED, no blocking defects found

Re-checked the Phase 7 foundations the master prompt requires before any public polish:
study config, dataset versioning, leakage audit, deterministic evaluation, NaN-safe metrics,
model/dataset cards, reproducibility metadata, research report, synthetic-model warnings all
exist and were verified working in the Phase 7 session (325 backend / 86 frontend tests green,
real Postgres + real uvicorn process exercised). No new critical defect found this audit that
would block a safe public release. **Decision: do not reopen Phase 7 — proceed to Phase 8.**

## What's already done (do NOT redo)

Security/production controls that already exist and meet or nearly meet the master prompt's bar:

- **CORS**: environment-driven allowlist, not wildcard (`app/main.py:167-174`, `CORS_ORIGINS` env var).
- **Global exception handling**: `app/main.py:61-120` — `AppError`/`RequestValidationError`/
  `StarletteHTTPException`/catch-all `Exception` handlers; stack traces logged server-side only
  (`logger.exception`), never returned to the client.
- **JWT**: HS256, `sub/type/iat/exp/iss/aud/jti` claims, 32-char min secret enforced in
  production (`app/core/security.py`), weak-secret blocklist, refresh-token rotation
  (single-use, revokes old session same transaction).
- **Settings fail-fast validation** (`app/core/config.py`): JWT secret strength, production
  forbids synthetic/non-required model, production forbids dev-seed env vars, DB URL scheme
  enforced.
- **Request size / image safety**: 5 MB upload cap, 4096×4096 max / 32×32 min / 16.7M pixel cap,
  EXIF stripped by rebuilding from a fresh pixel buffer (`medrisk_inference/image_validation.py`).
- **Health endpoints**: `/health/live` (no DB), `/health/ready` (DB + model status), `/health/model`
  — all already return safe, non-sensitive shapes.
- **Docker**: all three images (`Dockerfile`, `Dockerfile.inference`, `Dockerfile.ml`) already run
  as non-root `medrisk` user, no secrets copied in, no `--reload`/debug, healthchecks present,
  model/dataset artifacts mounted not baked in.
- **Frontend auth storage**: access token in memory only, refresh token in `sessionStorage` only
  (documented fallback rationale already in code comments), logout clears both + React Query cache.
- **Frontend public/private boundary already exists**: `/`, `/how-it-works`, `/technology`,
  `/model`, `/privacy`, `/limitations`, `/accessibility`, `/status`, `/login`, `/register` are
  public; everything under `/app/*` is wrapped in `ProtectedRoute`. No `dangerouslySetInnerHTML`
  anywhere in the frontend.
- **Disclaimers already in place**: landing page kicker + body, `common.json` `disclaimer` key,
  mandatory `researchNotice` checkbox at registration, `/model` page explicitly states
  "predictions have no medical meaning whatsoever."
- **No secrets in repo**: `.env`/`.env.*` gitignored, `.env.example` has placeholders only,
  `.dockerignore` excludes `.env*`, no hardcoded passwords found in frontend source.
- **`docs/security.md`** already covers password hashing, JWT/refresh handling, secret
  management, logging rules, no-real-patient-data policy, and an honest "known limitations" list
  (no login rate limiting, no account lockout, no CSRF needed, no access-token revocation).
- **`docs/decisions/ADR-001-backend-architecture.md`**, **`docs/inference-security.md`** (upload
  threat model), **`docs/model-deployment.md`** (registry/audit-trail/no-hot-swap) already exist
  and should be linked from new Phase 8 docs, not duplicated.
- **README** already has an explicit research-only disclaimer and an honest license line
  ("No license has been chosen yet ... all rights reserved").
- **`SECURITY.md`** already exists with a realistic personal-project scope statement.

## Real gaps found (Phase 8 scope, confirmed against current code — not assumed)

Security:
- No rate limiting anywhere (no `slowapi`/`limits`, confirmed by grep) — login, inference,
  Grad-CAM, report/audit endpoints are all unprotected against abuse.
- No role/admin distinction: any authenticated user can trigger
  `POST /research/datasets/{id}/quality-audit`, `.../leakage-audit`, and `POST
  /research/evaluations` — these are resource-creating/compute-triggering actions currently gated
  only by "is logged in," not ownership or role.
- No `docs/THREAT_MODEL.md` (formal STRIDE-style asset/trust-boundary doc) — existing
  `inference-security.md`/`security.md` are policy docs, not a structured threat model.
- No CI secret scanning, dependency audit (`pip-audit`/`npm audit`), or container scan.
- No CSP / security-header configuration anywhere (no deployment target exists yet to attach
  headers to).
- No `/version` endpoint (only `/health/*`).

Process / docs:
- No LICENSE file (README/`pyproject.toml` agree: unlicensed, intentional — needs the repo
  owner's explicit decision per the master prompt's own rule against auto-picking MIT/Apache/GPL).
- Missing: `docs/ARCHITECTURE.md` (a system-level one — current `architecture.md` is backend-layer
  only), `docs/SECURITY_AUDIT.md`, `docs/DEPLOYMENT.md`, `docs/OPERATIONS_RUNBOOK.md`,
  `docs/RELEASE_CHECKLIST.md`, `docs/DATABASE_RELEASE_AND_ROLLBACK.md`,
  `docs/DATA_AND_MODEL_PROVENANCE.md`, `docs/PORTFOLIO_CASE_STUDY.md`,
  `docs/KNOWN_LIMITATIONS.md`, `docs/DEMO_VIDEO_SCRIPT.md`, `CONTRIBUTING.md`, `CHANGELOG.md`,
  `CITATION.cff`.
- No deployment target chosen or deployed — Phase 8 cannot claim `VERIFIED-DEPLOYMENT` for
  anything until the user picks a real (free-tier, no paid resources) target and credentials are
  available. This is an external blocker, not something fixable by editing the repo alone.
- No browser-automation tool available in this environment (same gap as every prior phase,
  4 through 7) — accessibility/responsive/visual verification will again be `NOT-VERIFIED` or
  substituted with RTL + manual reasoning unless this changes.

## What Phase 8 will deliberately NOT change

- Will not touch Phase 1-7 database schema, model artifacts, dataset manifests, or evaluation
  results.
- Will not introduce a new package manager, ORM, or framework.
- Will not pick a LICENSE without the repo owner's explicit choice.
- Will not attempt a real deployment without explicit user instruction and available credentials.
- Will not add paid APIs, paid cloud resources, or analytics/tracking.

## User-selected scope for this session

Asked the repository owner which subset of the 26-section master prompt to prioritize (the
full scope is multi-session). Selected: **security hardening**, **CI/Docker/operational
readiness**, **portfolio docs/README/case study**. Deliberately deferred this session:
**actual deployment** (needs the owner's real account/credentials — see
[DEPLOYMENT.md](DEPLOYMENT.md)). License decision: **leave unlicensed** (owner's explicit
choice, recorded so a future session doesn't re-ask).

## Completed this session

**Security hardening:**
- `app/core/rate_limit.py` (new) — per-process sliding-window rate limiter, no new
  dependency. Wired into `POST /auth/register`, `/auth/login`, `/auth/refresh`,
  `POST /predictions/histopathology`, `POST /datasets/{id}/samples/{id}/predict`, and the
  three research write endpoints. Settings: `RATE_LIMIT_ENABLED` (default `true`, forced
  `false` for the whole test session in `tests/conftest.py`),
  `RATE_LIMIT_LOGIN_PER_MINUTE`/`_REGISTER_`/`_INFERENCE_`/`_RESEARCH_WRITE_`.
- `app/api/dependencies.py::get_current_superuser`/`CurrentSuperuserDep` (new) — enforces the
  pre-existing-but-unused `User.is_superuser` column on `POST .../quality-audit`,
  `.../leakage-audit`, `/research/evaluations`. `scripts/promote_superuser.py` (new) is the
  only way to grant it.
- `GET /version` (new, in `app/api/v1/endpoints/health.py`) — safe release metadata,
  `git_commit`/`model_version` are `None` (never fabricated) unless genuinely available.
  `GIT_COMMIT_SHA` build ARG added to `Dockerfile`/`Dockerfile.inference`.
- `docs/THREAT_MODEL.md` (new) — assets/trust-boundaries/26-row threat table, each row
  classified `Verified-repository`/`Verified-test`/`Partially verified`/`Not-verified`.
- `docs/SECURITY_AUDIT.md` (new) — self-administered audit, explicitly distinguished from a
  penetration test. 9 findings (F-1 through F-9), all Low/Medium, all either remediated this
  session or accepted-with-justification (notably **F-4**: `torch==2.11.0` has
  `CVE-2025-3000` (medium, `torch.jit.script` memory corruption) — verified via `pip-audit`
  + `WebSearch`, then verified by grep that this codebase never calls `torch.jit.script` —
  ignored in CI with `--ignore-vuln CVE-2025-3000`, documented, not silently suppressed).
- `.secrets.baseline` (new, via `detect-secrets scan`) — audited-format hashes only.

**CI/Docker/operational readiness:**
- `.github/workflows/ci.yml`: added workflow-level `permissions: contents: read`; added a
  **`frontend`** job (typecheck/lint/format/test/build — previously frontend had **no CI
  coverage at all**, a real gap this audit found); added a **`security`** job
  (`pip-audit` ×3 requirement files, `detect-secrets` diffed against the baseline,
  `npm audit --audit-level=high`).
- `docs/DEPLOYMENT.md` (new) — decision doc only, no live deploy. Chose Render as the
  candidate target with repo-specific reasoning; documented the **real** release blocker
  (`Settings.ENVIRONMENT` is a closed `Literal` and the only model bundle is
  `synthetic_only=true`, so `ENVIRONMENT=production` cannot legally serve it) rather than a
  generic "deploy later" placeholder.
- `docs/OPERATIONS_RUNBOOK.md` (new) — health checks, admin promotion, JWT rotation,
  troubleshooting `503`/`429`/`403`.
- `docs/DATABASE_RELEASE_AND_ROLLBACK.md` (new) — 4 rollback types disambiguated, migration
  reversibility classification, verified `alembic current`/`alembic check` this session.

**Portfolio docs:**
- `docs/KNOWN_LIMITATIONS.md`, `docs/DATA_AND_MODEL_PROVENANCE.md`,
  `docs/PORTFOLIO_CASE_STUDY.md` (all new).
- `README.md` rebuilt — it had **stopped documenting at Phase 3** (claimed "no
  frontend/dashboard" as a current limitation despite Phases 4-7 already having shipped one).
  Now covers Phases 4-8, frontend setup, the new CI jobs, a documentation map, and links to
  every new doc instead of duplicating their content inline.
- `CONTRIBUTING.md`, `CHANGELOG.md` (phase-by-phase, dated from real `git log`), `CITATION.cff`
  (new) — `CITATION.cff` deliberately uses the GitHub handle `gigix119`, not the repo owner's
  personal email, even though that email is the configured git author (avoids newly
  broadcasting it in a prominent file).
- Updated `docs/security.md`, `docs/inference-security.md`, `docs/database.md` in place to
  remove now-stale "no rate limiting"/"`is_superuser` unused" statements rather than leaving
  two documents disagreeing.

**Test coverage added:** `tests/unit/test_rate_limit.py` (4 tests, deterministic `now`
injection — no real sleeping), `tests/integration/test_research_authorization.py` (5 tests:
3 deny-by-default for non-admin, 1 admin-allowed, 1 unauthenticated-401). Updated existing
`tests/integration/test_research_dataset_audits.py`/`test_research_evaluations.py` to use a
new `superuser_auth_tokens` fixture (`tests/integration/conftest.py`) for the POST calls that
are now admin-gated.

## Verification performed this session

- `python scripts/check.py` (ruff format/check, mypy, pytest+coverage): **334 passed, 2
  skipped** (same 2 pre-existing platform-symlink skips as Phase 7) — up from 325 because of
  the new test files; zero lint/type regressions.
- `npm run check` in `frontend/`: **86 passed**, typecheck/lint/format/build all clean.
  `npm run api:generate` re-run to pick up the new `/version` schema.
- `pip-audit -r requirements.txt` (clean), `-r requirements-inference.txt` /
  `-r requirements-ml.txt` (1 ignored, documented finding each — see F-4 above).
- `npm audit --audit-level=high` in `frontend/`: clean (2 moderate findings below threshold,
  documented as F-9 — `@redocly/openapi-core`/`js-yaml`, dev-only tool, never shipped).
- `detect-secrets scan --baseline .secrets.baseline` round-trip: confirmed exits clean with
  no new findings against the just-generated baseline.
- `python -c "import yaml; yaml.safe_load(...)"` against the edited `ci.yml`: valid YAML.
- **Not verified this session** (documented, not hidden): the new `security`/`frontend` CI
  jobs have not yet run on a real GitHub Actions runner (first real run happens on the next
  push/PR — see `docs/SECURITY_AUDIT.md` "Known gaps").

## What Phase 8 did NOT do this session (deferred, not forgotten)

- No actual deployment (user-deferred — see [DEPLOYMENT.md](docs/DEPLOYMENT.md)).
- No CSP/security-header configuration (no deployed origin exists to attach headers to).
- No accessibility/responsive manual browser pass (no browser-automation tool available in
  this environment — same gap as every prior phase).
- No `docs/ARCHITECTURE.md` system-level diagram beyond the Mermaid one in
  `docs/PORTFOLIO_CASE_STUDY.md` (the existing `docs/architecture.md` is backend-layer-only
  and was judged sufficient combined with the case study's diagram, rather than adding a
  third, likely-overlapping document).
- No `docs/RELEASE_CHECKLIST.md` or `docs/DEMO_VIDEO_SCRIPT.md` — judged lower-value than the
  items actually completed, given the session's selected scope; not started.
- LICENSE file: explicitly left unlicensed per the owner's choice (not a gap — a decision).

## Next exact action required

Pick up the deferred items above in priority order: (1) watch the next CI run on GitHub
Actions to confirm the new `frontend`/`security` jobs actually pass in that environment
(local reasoning only so far); (2) if/when the owner decides to deploy, follow
[DEPLOYMENT.md](docs/DEPLOYMENT.md)'s "Next exact action required" section; (3) consider
`docs/RELEASE_CHECKLIST.md` once a real deployment target exists (a checklist for a
deployment that doesn't exist yet would be premature).

## Running log

- **2026-06-26** — Ran the full repository/Phase-7-gate audit (this file's content above) via
  direct git/glob inspection plus 4 parallel read-only Explore agents covering backend security,
  Docker/CI, frontend security/routing, and documentation/licensing. No code changes made yet.
- **2026-06-26** (same day, continued) — Asked the owner to prioritize scope (see "User-selected
  scope" above), then implemented rate limiting, admin authorization, `/version`, CI
  frontend+security jobs, and the full Phase 8 documentation set described above. Verified
  backend (334/2 skipped) and frontend (86/86) gates green, plus `pip-audit`/`npm audit`/
  `detect-secrets` all clean or documented. Nothing committed or pushed (not requested).
