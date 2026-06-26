# Operations runbook

Practical "how do I actually run/operate this" reference, for whoever (including future-me)
needs to operate this project without re-reading every phase's progress doc. Architecture
detail lives in [architecture.md](architecture.md)/[ml-architecture.md](ml-architecture.md)/
[inference-architecture.md](inference-architecture.md); this file is procedures, not design.

## Starting the stack locally

```bash
# No-model API (fastest, no PyTorch):
docker compose -f compose.yaml up -d --build

# Full inference stack (API + synthetic model + Grad-CAM):
docker compose -f compose.inference.yaml up -d --build
```

Both bring up `db` (Postgres 16) and `api`, run `wait_for_db` → `alembic upgrade head` →
the two idempotent seed scripts → Uvicorn, in that order, via the Compose command chain. See
[development.md](development.md) for the non-Docker local setup.

## Health checks

```bash
curl http://localhost:8000/health/live    # process is up - no DB, no model check
curl http://localhost:8000/health/ready   # DB reachable + (if MODEL_REQUIRED) model ready
curl http://localhost:8000/health/model   # model runtime status, never the bundle path
curl http://localhost:8000/version        # app/environment/git-commit/model version - never fabricated
```

`/health/ready` returns `503` (not `200` with a "not ready" body) when a required dependency
is down — check the HTTP status code, not just the JSON shape, in any monitoring config.

## Creating the first administrator account

There is no API endpoint to grant `is_superuser` (by design — see
[THREAT_MODEL.md](THREAT_MODEL.md)). After registering a normal account through
`/auth/register` (or the frontend `/register` page):

```bash
python -m scripts.promote_superuser admin@example.com
# or, to revoke:
python -m scripts.promote_superuser admin@example.com --revoke
```

Run this against whichever database the process's `DATABASE_URL`/`ENVIRONMENT` currently
points at — there is no `--database-url` override; set the environment the same way you
would for any other one-off script in this project.

## Local-dev seeding (never in production)

`scripts/seed_dev_user.py` and `scripts/seed_dataset.py` both no-op (exit 0, log a message)
when `ENVIRONMENT=production`, and `Settings.validate_dev_seed_not_in_production`
independently hard-fails startup if `DEV_SEED_USER_EMAIL`/`PASSWORD` are set in that
environment — defense in depth, not a single point of failure. Both scripts are idempotent;
re-running them after a restart never duplicates the dev user or the 50 synthetic dataset
samples.

## Rotating the JWT secret

1. Generate a new one: `python -c "import secrets; print(secrets.token_urlsafe(64))"`.
2. Set the new value as `JWT_SECRET_KEY` and restart the API process.
3. **Every currently-issued access and refresh token becomes invalid immediately** — there
   is no dual-secret grace period in this implementation. Plan for all logged-in users
   needing to log in again. This is an accepted trade-off for keeping the JWT verification
   logic in `app/core/security.py` simple; revisit if this project ever needs zero-downtime
   secret rotation.

## Diagnosing a `503` from `/health/ready`

1. Check the response body's `dependencies` map — it names which dependency failed
   (`database` or `histopathology_model`).
2. **Database unreachable**: check `DATABASE_URL`, check the Postgres container/service is
   up, check `pg_isready`.
3. **Model not ready**: check `MODEL_BUNDLE_PATH` points at a real, mounted directory; check
   the API process's startup logs for `BundleInvalidError` (checksum mismatch, missing file,
   symlink escape, or a synthetic bundle with `ALLOW_SYNTHETIC_MODEL=false`) — see
   [model-deployment.md](model-deployment.md).

## Diagnosing a `429` (rate limit)

New in Phase 8 — `app/core/rate_limit.py`. The response includes a `Retry-After` header
(seconds). Remember this is **per-process, in-memory** (`docs/SECURITY_AUDIT.md` /
`docs/THREAT_MODEL.md`): if the deployment ever runs more than one worker process or
replica, a client could in principle exceed the *intended* aggregate limit by hitting
different processes, even though each individual process enforces its own limit correctly.
Tune `RATE_LIMIT_*_PER_MINUTE` env vars (see `.env.example`) per environment; do not disable
`RATE_LIMIT_ENABLED` outside the test environment.

## Diagnosing a `403 AUTHORIZATION_FAILED` on a research write endpoint

The caller is authenticated but `is_superuser=false`. This is expected for any non-admin
account on `POST .../quality-audit`, `.../leakage-audit`, `.../evaluations` — promote the
account (see above) if it genuinely needs to run audits/create evaluations, or use the
`medrisk_research` CLI directly against the database if the action doesn't need to go
through the live API at all (see `docs/PHASE_7_PROGRESS.md` for why most real evaluation work
is CLI-only regardless of this check).

## Routine maintenance

- **Dependency updates**: `pip-audit`/`npm audit` now run on every push/PR (`security` CI
  job) — check the Actions tab periodically even without a code change, since a new CVE can
  appear in an already-merged dependency.
- **Coverage artifacts**: `htmlcov/`, `.coverage`, `coverage.xml` are local/CI-generated and
  gitignored — safe to delete locally at any time; they're regenerated by the next test run.
- **`artifacts/` directory**: `datasets/`, `model_registry/`, `registry/`, `experiments/` are
  gitignored (only `.gitkeep` placeholders are tracked) — local runs populate them; do not
  assume a fresh clone has any of this data until the relevant seed/training command has run.

## Logs

Human-readable (not yet structured JSON — documented limitation, see
[security.md](security.md) "Known limitations"). Never search logs expecting to find a
password, JWT, `Authorization` header, or raw refresh token — they are never written there by
design; if one ever appears, treat it as a bug, not a feature to rely on.
