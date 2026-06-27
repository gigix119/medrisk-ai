# Deployment

## Render deployment

A `render.yaml` Blueprint exists in the repository root and implements the "Chosen target"
decision below. It is a config file, not a deployment record - see the rest of this document
for what is and isn't actually deployed.

**Blueprint approach.** Render reads `render.yaml` and provisions two resources from it: a
`medrisk-db` managed PostgreSQL 16 database, and a `medrisk-api` web service built from the
repository's plain `Dockerfile` (no PyTorch/inference runtime - the initial deployment runs
with `MODEL_REQUIRED=false` and serves no real predictions; see
[model-deployment.md](model-deployment.md) and `Dockerfile.inference` for what switching to
real inference later would involve). The service's `dockerCommand` runs
`alembic upgrade head` once per deploy and then starts Uvicorn bound to Render's `$PORT`. In
the Render dashboard: New → Blueprint → point at this repository → Render parses
`render.yaml` and shows a plan before creating anything.

`render.yaml` deliberately uses `ENVIRONMENT=development`, not `production`. The repository's
only model bundle is synthetic-only, and `Settings.validate_production_model_policy`
(`app/core/config.py`) refuses to start with `ENVIRONMENT=production` unless
`MODEL_REQUIRED=true` *and* `ALLOW_SYNTHETIC_MODEL=false` - a combination this repository
cannot satisfy without a real trained model. `ENVIRONMENT=development` with
`MODEL_REQUIRED=false` is the honest, currently-correct choice for "deployed, but with no
inference yet"; see "What deploying would require," point 3, below for the full reasoning.

**Variables that must be set manually in the Render dashboard.** `render.yaml` marks these
`sync: false`, meaning Render will prompt for a value at Blueprint creation time and never
overwrite it on redeploy:

- `JWT_SECRET_KEY` - no safe default exists outside the test environment. Generate one
  locally and paste it in:
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(64))"
  ```
- `DATABASE_URL` - see the next section; it cannot be wired automatically from the managed
  database because of a connection-string scheme mismatch.

**Setting `DATABASE_URL` from the Render managed PostgreSQL connection string.** Render's
Postgres "Internal Connection String" (use this, not the external one, since the API and
database run in the same Render private network) looks like:

```
postgresql://medrisk:<password>@<host>/medrisk
```

`app/core/config.py`'s `validate_database_url_scheme` requires the `postgresql+asyncpg://`
scheme (this project uses SQLAlchemy's async driver throughout), so take the Internal
Connection String from the `medrisk-db` database's Render dashboard page and change only the
scheme prefix:

```
postgresql+asyncpg://medrisk:<password>@<host>/medrisk
```

Paste the result as `medrisk-api`'s `DATABASE_URL` value. This is also why `render.yaml`
cannot use a `fromDatabase: connectionString` reference for this variable - Render's
generated string and this app's required scheme don't match, and Blueprint syntax has no way
to rewrite a referenced value in place.

**No real model bundle is deployed.** The Docker image built from the plain `Dockerfile`
contains no model weights and no PyTorch runtime (see the image's own header comment).
`MODEL_REQUIRED=false` in `render.yaml` reflects that honestly: the deployed instance starts
and serves every endpoint except real inference, rather than failing startup or silently
serving a synthetic prediction as if it were real. Do not set `MODEL_REQUIRED=true` or
`ALLOW_SYNTHETIC_MODEL=true` for this deployment without first rebuilding from
`Dockerfile.inference` and making the deliberate, documented decision described in "Chosen
target" and "What deploying would require" below - the synthetic bundle's lack of medical
meaning must stay as visible in a deployed instance as it already is in this repository's
disclaimers.

---

**Status: not deployed. No live URL exists for this project as of this writing.** This
document records the deployment *decision* (what target, why, what's required) so the next
session can execute it, rather than re-litigate it — per the Phase 8 ground rules, actually
deploying requires the repository owner's explicit instruction and real account credentials,
neither of which this session had. See [PHASE_8_PROGRESS.md](PHASE_8_PROGRESS.md).

Do not infer from this document that a deployment happened. Every claim below is either
`VERIFIED-REPOSITORY` (true about the code today) or explicitly marked `BLOCKED`/`NOT
DONE`.

## What already exists (VERIFIED-REPOSITORY)

- Two runnable container images: `Dockerfile` (API only) and `Dockerfile.inference` (API +
  PyTorch inference runtime). Both are non-root, healthchecked, and accept a
  `GIT_COMMIT_SHA` build arg (Phase 8) for `GET /version`.
- Two Compose files (`compose.yaml`, `compose.inference.yaml`) that already model a
  realistic two-service (Postgres + API) topology with health-gated startup ordering.
- A `Dockerfile.ml` for offline training/evaluation — never deployed as a running service;
  it's a CLI image, not a server.
- A working CI pipeline (`test`, `ml`, `frontend`, `security` jobs) that proves the backend
  and frontend each build and pass their gates — but **does not deploy anything**; there is
  no deploy job, no cloud credentials referenced, no environment secret consumed by CI.

## Chosen target (decision, not yet executed)

**Render** (free/hobby tier web service + managed Postgres), as a single coherent path,
chosen over alternatives for these repo-specific reasons:

- The app is already a single Dockerized FastAPI service + Postgres — Render's "Web
  Service + PostgreSQL" pairing maps onto that directly with no architecture change.
- No paid resources required at hobby tier (consistent with the "no paid APIs/cloud
  resources" constraint).
- Render builds directly from a Dockerfile in the repo (`Dockerfile.inference`, since the
  public demo needs real — if synthetic — inference, not the no-model `Dockerfile`), so the
  existing image is reused unmodified rather than rewritten for a platform-specific buildpack.

Other targets considered and rejected for this repo specifically:

- **Fly.io** — equally viable technically; Render was chosen only because its free Postgres
  tier doesn't require a separate volume-attached VM the way Fly's Postgres does, which is
  simpler for a single-maintainer portfolio project.
- **Vercel/Netlify** — frontend-only; would still need a separate backend host, so picking
  one of those for the frontend without first deciding the backend host doesn't simplify
  anything overall. Revisit if the frontend and backend end up on different platforms.
- **AWS/GCP/Azure free tier** — viable but adds IAM/VPC/security-group configuration that is
  disproportionate to a single-instance demo and risks accidentally leaving a paid resource
  running. Rejected for this project's scale.

## What deploying would require (BLOCKED — needs the repository owner)

1. A Render account (or chosen alternative) — not something this session can create.
2. Real production secrets: a strong `JWT_SECRET_KEY` (32+ chars, generated fresh — never
   reuse the local dev one), `CORS_ORIGINS` set to the real deployed frontend origin (no
   wildcard), `ALLOWED_HOSTS` set to the real hostname.
3. A decision about `ENVIRONMENT`. `Settings.ENVIRONMENT` is a closed
   `Literal["development", "test", "production"]` (`app/core/config.py:14`) — there is no
   fourth "public demo" value today. The **only** model bundle in this repository is
   `synthetic_only=true` (`artifacts/model_registry/smoke-baseline-cnn/0.0.1-smoke/`), and
   `validate_production_model_policy` (`app/core/config.py:148-159`) refuses to start with
   `ENVIRONMENT=production` unless `MODEL_REQUIRED=true` and `ALLOW_SYNTHETIC_MODEL=false` —
   a combination this repository's only artifact cannot satisfy. **This is the real release
   blocker**, not a missing deployment step: there is no real (non-synthetic) trained model
   to deploy as production-grade today. The honest options are (a) deploy the public demo
   with `ENVIRONMENT=development` and `ALLOW_SYNTHETIC_MODEL=true` — accurate, since the
   model genuinely isn't production-grade, but means the production-hardening guards in
   `validate_production_model_policy`/`validate_dev_seed_not_in_production` don't apply, so
   `DEV_SEED_USER_EMAIL`/`PASSWORD` must be left unset manually rather than relying on that
   guard — or (b) train/obtain a real model first and deploy with `ENVIRONMENT=production`
   as the guard intends. Do not add a fourth `ENVIRONMENT` value just to relabel a synthetic
   deployment as something it isn't.
4. A managed Postgres instance + running the Alembic migration chain once
   (`alembic upgrade head`) against it before first boot.
5. DNS/TLS — out of scope per the Phase 8 ground rules (no domain purchase, no DNS changes
   without explicit instruction); Render's default `*.onrender.com` subdomain with
   Render-managed TLS is the simplest path that needs neither.
6. CSP/security headers configured at the platform/proxy level once a real origin exists —
   tracked as a known gap in [SECURITY_AUDIT.md](SECURITY_AUDIT.md), not yet actionable
   without a deployed origin to attach headers to.

## Recommended honest framing for the public demo

Given finding #3 above, the most scientifically honest path is **not** "deploy a production
model" but "deploy the existing, already-labeled synthetic research demo publicly" — which
this project's frontend and API already support end-to-end (every surface already says
`synthetic_only`/`is_synthetic` explicitly). The release blocker is not technical; it's that
no real trained model exists yet, and Phase 8's own rules forbid fabricating one to look more
impressive ("do not train a large model during this milestone").

## Next exact action required (for whoever picks this up)

1. Confirm with the repository owner whether to deploy the synthetic demo as-is (clearly
   labeled) or wait for a real trained model.
2. If proceeding: create the Render account/services, generate real secrets, set environment
   variables per `.env.example`, run migrations once against the managed Postgres, deploy
   `Dockerfile.inference` pointed at the synthetic bundle with `MODEL_REQUIRED=true`,
   `ALLOW_SYNTHETIC_MODEL=true`, and `ENVIRONMENT=development` (see option (a) above — do
   not use `ENVIRONMENT=production` for a synthetic-model deployment; the Settings guard is
   deliberately strict here and a fourth environment value should not be invented to work
   around it).
3. Open the real deployed URL in a browser and verify the golden path (landing → demo →
   prediction → Grad-CAM → model/dataset cards) before claiming `VERIFIED-DEPLOYMENT`
   anywhere.
