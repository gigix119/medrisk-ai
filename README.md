# MedRisk AI

An educational and research platform for a future oncology AI system. This repository contains **Phase 1: Backend Foundation** (a production-conscious FastAPI + PostgreSQL backend with authentication, request/error handling, migrations, tests, and CI) and **Phase 2: Histopathology ML Foundation** (a standalone, reproducible PyTorch pipeline for binary histopathology image classification — data, models, training, evaluation, calibration, Grad-CAM explainability, and a local model registry). The two are independent: nothing in `app/` imports from `medrisk_ml/` or vice versa. The trained model is **not** wired into the API yet — that is Phase 3.

> **Medical disclaimer.** This software is an educational and research portfolio project. It is **not a medical device** and must not be used for diagnosis, treatment decisions, or emergency medical guidance. Prediction endpoints in the API are honest placeholders that explicitly report that no model is loaded — they never return a fake medical result. Any metric produced from synthetic data in Phase 2 is explicitly **not** a measurement of real diagnostic performance — see [docs/dataset-card-pcam.md](docs/dataset-card-pcam.md).

## Table of contents

1. [Phase 1 scope](#phase-1-scope)
2. [Phase 2 scope](#phase-2-scope)
3. [Roadmap](#roadmap)
4. [Architecture overview](#architecture-overview)
5. [Technology stack](#technology-stack)
6. [Repository structure](#repository-structure)
7. [Prerequisites](#prerequisites)
8. [Setup — Windows (PowerShell)](#setup--windows-powershell)
9. [Setup — Linux/macOS](#setup--linuxmacos)
10. [Environment configuration](#environment-configuration)
11. [Docker Compose setup](#docker-compose-setup)
12. [Database migrations](#database-migrations)
13. [Running the API](#running-the-api)
14. [Tests](#tests)
15. [Lint and type checking](#lint-and-type-checking)
16. [API endpoints](#api-endpoints)
17. [Authentication example](#authentication-example)
18. [API documentation](#api-documentation)
19. [ML pipeline setup](#ml-pipeline-setup)
20. [ML pipeline usage (CLI)](#ml-pipeline-usage-cli)
21. [Real PCam dataset (gated)](#real-pcam-dataset-gated)
22. [Dependencies](#dependencies)
23. [Security notes](#security-notes)
24. [Development workflow](#development-workflow)
25. [Current limitations](#current-limitations)
26. [License](#license)

## Phase 1 scope

This phase builds the backend foundation: project structure, configuration, FastAPI app, async PostgreSQL access, authentication (JWT access/refresh tokens with rotation), a prediction-history data model, tests, Docker, and CI. See [docs/project-scope.md](docs/project-scope.md) for the detailed in/out-of-scope list.

## Phase 2 scope

This phase builds a complete, reproducible, explainable ML pipeline for binary histopathology classification (PatchCamelyon / PCam: tumor tissue present/absent in a patch's center region) — entirely independent of the Phase 1 API:

- Typed, validated experiment configuration (pydantic, `extra="forbid"`, YAML + CLI overrides).
- A from-scratch baseline CNN and a ResNet18 transfer-learning model (staged freeze/unfreeze), both returning raw single-logit outputs.
- A training engine with early stopping, checkpointing, gradient clipping/accumulation, mixed precision, LR scheduling, and full reproducibility metadata.
- Leakage-safe evaluation: decision-threshold selection and temperature-scaling calibration fit on the validation split only, a single frozen evaluation on the test split, bootstrap confidence intervals, plots, and error analysis.
- Grad-CAM explainability, implemented from scratch, with a mandatory disclaimer on every output.
- A local, file-based experiment registry and model registry, plus a portable, self-verifying model bundle.
- A safety-gated real-PCam path (never downloaded automatically) and a fully synthetic data path for fast iteration, tests, and CI — never conflated with real performance.

See [docs/ml-architecture.md](docs/ml-architecture.md) for the full design and [docs/learning/phase-02-histopathology-ml.md](docs/learning/phase-02-histopathology-ml.md) for a guided, Polish-language walkthrough of every ML concept used.

## Roadmap

1. ~~Histopathology image classification (CNN / transfer learning).~~ — Phase 2
2. ~~Grad-CAM model explainability.~~ — Phase 2
3. ~~Model quality/error analysis.~~ — Phase 2
4. Wiring a registered model into the API for real inference (not part of this repository yet).
5. An optional, separate survival-analysis module.
6. A user-facing dashboard.
7. Model versioning and prediction monitoring in production.

## Architecture overview

The backend is a modular monolith: API → service → repository → database, with a clear request/auth/error-handling pipeline. Full details and a request-flow diagram: [docs/architecture.md](docs/architecture.md). The ML pipeline is a separate, layered package (config → data → models → training → evaluation/explainability → registry); full details and a pipeline-flow diagram: [docs/ml-architecture.md](docs/ml-architecture.md).

## Technology stack

**Backend:**
- **Python 3.12** (3.11-compatible)
- **FastAPI** + **Uvicorn**
- **Pydantic v2** / **pydantic-settings**
- **SQLAlchemy 2.0** (async, typed ORM) + **asyncpg**
- **Alembic** (migrations)
- **PostgreSQL 16**
- **PyJWT** + **pwdlib[argon2]** (JWT + Argon2 password hashing)
- **pytest** / **pytest-asyncio** / **pytest-cov** / **HTTPX**

**ML pipeline (Phase 2):**
- **PyTorch** + **torchvision** (CPU build pinned in `requirements-ml.txt`; a local CUDA build is also supported and not downgraded by it)
- **NumPy** / **pandas** / **Pillow** / **scikit-learn** / **matplotlib**
- **h5py** (PCam's HDF5 storage format, via `torchvision.datasets.PCAM`)
- **tqdm** (progress bars) / **TensorBoard** (training curves)

**Shared tooling:**
- **Ruff** (lint + format) / **mypy** (types, strict mode, covers both `app` and `medrisk_ml`)
- **Docker** / **Docker Compose**
- **GitHub Actions** (CI)

## Repository structure

```text
medrisk-ai/
├── app/                  FastAPI application (api, core, db, middleware, models, repositories, schemas, services)
├── medrisk_ml/           ML pipeline (config, data, models, training, evaluation, explainability, registry, utils, cli.py)
├── configs/ml/           Experiment YAML configs (smoke, baseline_cnn, resnet18)
├── scripts/ml/           Thin CLI wrappers (train, evaluate, explain, register_model, verify_bundle, download_pcam, inspect_dataset)
├── alembic/              Database migrations
├── docker/postgres/      PostgreSQL container init script
├── docs/                 Architecture, database, API contract, security, ADRs, ML docs, learning guides
├── docs/learning/        Polish-language, concept-by-concept guided walkthroughs (Phase 1 and Phase 2)
├── scripts/              wait_for_db.py, check.py, dev.ps1, dev.sh
├── tests/                unit/, integration/ (backend) and ml/ (ML pipeline) tests
├── artifacts/            Generated experiments, registries, model bundles (git-ignored contents)
├── data/                 Dataset storage: external/, interim/, processed/ (git-ignored contents)
├── .github/workflows/    CI pipeline
├── compose.yaml          Local PostgreSQL + API stack
├── Dockerfile            API container image
├── Dockerfile.ml         ML pipeline container image (CPU-only)
├── requirements-ml.txt   ML runtime dependencies (portable CPU pins)
└── pyproject.toml        Project metadata + tool configuration (Ruff, mypy, pytest, coverage)
```

## Prerequisites

- Python 3.12 (3.11 also works)
- PostgreSQL 16, reachable locally — either:
  - a native local install, or
  - Docker Desktop / Docker Engine + Compose
- Git (optional for this phase; no commits are required to run the project)

## Setup — Windows (PowerShell)

```powershell
# 1. Create and activate a virtual environment
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1

# 2. Install dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt

# 3. Configure environment
Copy-Item .env.example .env
# Edit .env: set a real JWT_SECRET_KEY, e.g.
python -c "import secrets; print(secrets.token_urlsafe(64))"

# 4. Set up PostgreSQL (native example; see docs/database.md for details)
#    Create role "medrisk" and databases "medrisk" + "medrisk_test",
#    matching whatever you put in .env.

# 5. Apply migrations
python -m alembic upgrade head

# 6. Run the API
python -m uvicorn app.main:app --reload
```

## Setup — Linux/macOS

```bash
# 1. Create and activate a virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt

# 3. Configure environment
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(64))"
# paste the output into .env as JWT_SECRET_KEY

# 4. Set up PostgreSQL (native, Docker, or Docker Compose — see below)

# 5. Apply migrations
python -m alembic upgrade head

# 6. Run the API
python -m uvicorn app.main:app --reload
```

## Environment configuration

All configuration is environment-driven (`app/core/config.py`, loaded via `pydantic-settings` from `.env`). Copy `.env.example` to `.env` and fill in real local values — `.env` is git-ignored and must never be committed.

Key variables (see `.env.example` for the full list with comments):

| Variable | Purpose |
|---|---|
| `ENVIRONMENT` | `development` \| `test` \| `production`. Selects `DATABASE_URL` vs `TEST_DATABASE_URL` and relaxes JWT-secret-strength validation only for `test`. |
| `DATABASE_URL` / `TEST_DATABASE_URL` | `postgresql+asyncpg://...` connection strings for the dev and test databases. |
| `JWT_SECRET_KEY` | **No safe default.** Must be a real, high-entropy secret outside the test environment, or the app refuses to start. |
| `CORS_ORIGINS` / `ALLOWED_HOSTS` | Comma-separated lists. |

There is intentionally no working default `JWT_SECRET_KEY` — generate one locally:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

## Docker Compose setup

```bash
docker compose config   # validate
docker compose build
docker compose up -d
docker compose ps
docker compose logs -f api
```

This starts PostgreSQL 16 (with both the `medrisk` and `medrisk_test` databases) and the API, waits for the database, runs `alembic upgrade head`, and starts Uvicorn. See [docs/architecture.md](docs/architecture.md) and the comments in `compose.yaml` for details — including a note about port `5432` conflicting with any native PostgreSQL install already running on the host.

> Docker Desktop is installed in this environment as of Phase 2 (it was not available during the original Phase 1 build). `docker build` has been verified for both `Dockerfile` (this API image) and `Dockerfile.ml` (the ML pipeline image) — both build successfully and their entrypoints run correctly (verified by importing `app.main` with required settings present, and by running a full synthetic smoke-training pass inside the ML image). Full `docker compose up` (API + PostgreSQL together) has not been re-verified in this session.

## Database migrations

```bash
alembic upgrade head      # apply all migrations
alembic current           # show the current revision
alembic check              # confirm no model changes are pending
alembic downgrade base    # roll back everything (local dev only)
alembic history            # list all revisions
```

Migrations never run automatically against a production database from application startup code — see [docs/database.md](docs/database.md).

## Running the API

```bash
python -m uvicorn app.main:app --reload
```

- Root: http://127.0.0.1:8000/
- Liveness: http://127.0.0.1:8000/health/live
- Readiness: http://127.0.0.1:8000/health/ready
- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc

## Tests

```bash
pytest                                          # run the full suite: backend (unit/integration) + ML (tests/ml)
pytest tests/unit tests/integration             # backend only
pytest tests/ml                                  # ML pipeline only (no real PCam download, no GPU required)
pytest --cov=app --cov-report=term-missing      # with coverage
pytest --cov=app --cov-report=html              # local HTML report (htmlcov/)
```

Backend integration tests run against a **real PostgreSQL test database** (`TEST_DATABASE_URL`) — never SQLite, never mocks. `tests/conftest.py` forces `ENVIRONMENT=test` before any app module is imported. ML tests run entirely against synthetic, generated data — no network access, no real dataset, deterministic.

## Lint and type checking

```bash
ruff format --check .
ruff check .
mypy app scripts medrisk_ml
```

Or run everything CI runs, in order, stopping at the first failure (covers both `app` and `medrisk_ml`):

```bash
python scripts/check.py
```

## API endpoints

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/` | — | Service info + medical disclaimer |
| GET | `/health/live` | — | Liveness (no DB check) |
| GET | `/health/ready` | — | Readiness (checks PostgreSQL) |
| POST | `/api/v1/auth/register` | — | Create a user |
| POST | `/api/v1/auth/login` | — | OAuth2 password form → access + refresh tokens |
| POST | `/api/v1/auth/refresh` | — | Rotate a refresh token |
| POST | `/api/v1/auth/logout` | — | Revoke a refresh session |
| GET | `/api/v1/users/me` | Bearer | Current user's profile |
| GET | `/api/v1/predictions/history` | Bearer | Paginated, user-scoped prediction history |
| POST | `/api/v1/predictions/histopathology` | Bearer | Honest `501` placeholder — no model loaded |
| POST | `/api/v1/predictions/survival` | Bearer | Honest `501` placeholder — no model loaded |

Full request/response contracts: [docs/api-contract.md](docs/api-contract.md).

## Authentication example

```bash
# Register
curl -X POST http://127.0.0.1:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"a-long-secure-password","full_name":"Example User"}'

# Log in (note: form-encoded, OAuth2 "username" field carries the email)
curl -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=user@example.com&password=a-long-secure-password"

# Call a protected endpoint
curl http://127.0.0.1:8000/api/v1/users/me \
  -H "Authorization: Bearer <access_token>"
```

PowerShell equivalent:

```powershell
$body = @{ email = "user@example.com"; password = "a-long-secure-password"; full_name = "Example User" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/auth/register -ContentType "application/json" -Body $body

$login = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/auth/login `
  -ContentType "application/x-www-form-urlencoded" `
  -Body "username=user@example.com&password=a-long-secure-password"

Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v1/users/me -Headers @{ Authorization = "Bearer $($login.access_token)" }
```

## API documentation

Interactive OpenAPI docs are served at `/docs` (Swagger UI, with a working "Authorize" button for Bearer tokens) and `/redoc`.

## ML pipeline setup

The ML pipeline (`medrisk_ml/`) has its own dependency set, separate from the API. It works inside the same `.venv` as the backend (no separate environment required):

```powershell
# Windows PowerShell — from an already-activated .venv (see Setup above)
python -m pip install -r requirements-ml.txt
python -m pip install -r requirements-ml-dev.txt   # only if you need mypy stubs for ML code

# Sanity check: confirms interpreter/library versions and GPU detection
python -m medrisk_ml.cli environment
```

`requirements-ml.txt` pins a portable **CPU** build of PyTorch/torchvision. If you have an NVIDIA GPU and want CUDA acceleration, install the matching CUDA build *after* the line above (it will not be downgraded by a later `pip install -r requirements-ml.txt`, since PyTorch's local version suffix, e.g. `2.11.0+cu128`, still satisfies a plain `==2.11.0` pin):

```powershell
python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
```

## ML pipeline usage (CLI)

Every ML operation goes through one CLI, `python -m medrisk_ml.cli <command>`. All commands below use **fully synthetic, generated data** (`configs/ml/smoke.yaml`) — no download, no GPU required, completes in well under a minute on CPU. See [docs/dataset-card-pcam.md](docs/dataset-card-pcam.md) for why synthetic results are never a medical-performance claim.

```powershell
# 1. Train (writes artifacts/experiments/<experiment_id>/...)
python -m medrisk_ml.cli train --config configs/ml/smoke.yaml

# 2. Evaluate the trained experiment (threshold/calibration fit on val, frozen, test run once)
python -m medrisk_ml.cli evaluate --experiment-id <experiment_id>

# 3. Generate Grad-CAM explainability overlays (with the mandatory disclaimer)
python -m medrisk_ml.cli explain --experiment-id <experiment_id>

# 4. Register the model into the local model registry + build a portable, self-verifying bundle
python -m medrisk_ml.cli register --experiment-id <experiment_id> --version 0.0.1

# 5. Independently verify a registered bundle (checksums + a smoke inference pass)
python -m medrisk_ml.cli verify-bundle --model-id <model_name>:0.0.1
```

`--set section.key=value` overrides any config field without editing the YAML file, e.g. `--set training.epochs=5 --set training.learning_rate=0.0005`. Full pipeline design: [docs/ml-architecture.md](docs/ml-architecture.md); the train/val/test leakage-prevention protocol: [docs/experiment-protocol.md](docs/experiment-protocol.md); metrics/calibration/plots: [docs/evaluation.md](docs/evaluation.md); Grad-CAM and its limits: [docs/explainability.md](docs/explainability.md).

## Real PCam dataset (gated)

The real PatchCamelyon dataset (~7 GB) is **never** downloaded automatically. It requires both an explicit CLI flag and an environment variable:

```powershell
$env:MEDRISK_ALLOW_DATA_DOWNLOAD = "1"
python -m medrisk_ml.cli data download --config configs/ml/resnet18.yaml --download
```

Missing either condition is a hard stop with an explanatory message, never a silent fetch. See [docs/dataset-card-pcam.md](docs/dataset-card-pcam.md) for the dataset's labeling rule and known biases, and [docs/experiment-protocol.md](docs/experiment-protocol.md) for the staged transfer-learning protocol (`configs/ml/resnet18.yaml`) intended to be used with it. Real-PCam training is never auto-executed by this repository or its CI.

## Dependencies

Every direct runtime/dev dependency and why it's here is documented inline in [requirements.txt](requirements.txt), [requirements-dev.txt](requirements-dev.txt), [requirements-ml.txt](requirements-ml.txt), and [requirements-ml-dev.txt](requirements-ml-dev.txt).

## Security notes

Password hashing (Argon2), JWT handling, refresh-token rotation, and secret management are documented in [docs/security.md](docs/security.md) and [SECURITY.md](SECURITY.md). No real patient data should ever be used with this project — see the disclaimer at the top of this file.

## Development workflow

- Branch from your default branch, open a PR — CI (`.github/workflows/ci.yml`) runs the backend job (migrations, `alembic check`, Ruff, mypy, pytest with coverage) and a separate ML job (Ruff, mypy, `pytest tests/ml`, all on synthetic data, no GPU, no real dataset).
- Run `python scripts/check.py` locally before pushing — covers both `app` and `medrisk_ml`.
- See [docs/decisions/ADR-001-backend-architecture.md](docs/decisions/ADR-001-backend-architecture.md) for why the backend stack looks the way it does, [docs/learning/phase-01-backend-foundation.md](docs/learning/phase-01-backend-foundation.md) for a guided, Polish-language walkthrough of every backend concept used, and [docs/learning/phase-02-histopathology-ml.md](docs/learning/phase-02-histopathology-ml.md) for the same treatment of every ML concept used in Phase 2.

## Current limitations

- No ML model is wired into the API; `predictions/*` inference endpoints always return `501`. A registered Phase 2 model bundle exists on disk but integrating it into the API is explicitly out of scope until Phase 3.
- No file/object storage, no image upload handling.
- The real PatchCamelyon dataset has not been downloaded in this environment — every Phase 2 result produced so far is from synthetic data only (see the disclaimer at the top of this file) or, where noted, an explicitly-run real-data experiment.
- Single PostgreSQL instance, no read replicas, no connection-pooling proxy (e.g. PgBouncer) — not needed at this scale yet.
- No survival-analysis module, no frontend/dashboard — neither is in scope for Phase 1 or Phase 2.

## License

No license has been chosen yet for this portfolio project. All rights reserved by the author until a license is added.
