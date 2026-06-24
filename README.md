# MedRisk AI

An educational and research backend for a future oncology AI platform. This repository currently contains **Phase 1: Backend Foundation** — a production-conscious FastAPI + PostgreSQL backend with authentication, request/error handling, migrations, tests, and CI. There is no machine learning model in this phase.

> **Medical disclaimer.** This software is an educational and research portfolio project. It is **not a medical device** and must not be used for diagnosis, treatment decisions, or emergency medical guidance. Prediction endpoints in this phase are honest placeholders that explicitly report that no model is loaded — they never return a fake medical result.

## Table of contents

1. [Phase 1 scope](#phase-1-scope)
2. [Roadmap](#roadmap)
3. [Architecture overview](#architecture-overview)
4. [Technology stack](#technology-stack)
5. [Repository structure](#repository-structure)
6. [Prerequisites](#prerequisites)
7. [Setup — Windows (PowerShell)](#setup--windows-powershell)
8. [Setup — Linux/macOS](#setup--linuxmacos)
9. [Environment configuration](#environment-configuration)
10. [Docker Compose setup](#docker-compose-setup)
11. [Database migrations](#database-migrations)
12. [Running the API](#running-the-api)
13. [Tests](#tests)
14. [Lint and type checking](#lint-and-type-checking)
15. [API endpoints](#api-endpoints)
16. [Authentication example](#authentication-example)
17. [API documentation](#api-documentation)
18. [Dependencies](#dependencies)
19. [Security notes](#security-notes)
20. [Development workflow](#development-workflow)
21. [Current limitations](#current-limitations)
22. [License](#license)

## Phase 1 scope

This phase builds the backend foundation: project structure, configuration, FastAPI app, async PostgreSQL access, authentication (JWT access/refresh tokens with rotation), a prediction-history data model, tests, Docker, and CI. See [docs/project-scope.md](docs/project-scope.md) for the detailed in/out-of-scope list.

## Roadmap

Future phases (not part of this repository yet):

1. Histopathology image classification (CNN / transfer learning).
2. Grad-CAM model explainability.
3. Model quality/error analysis.
4. An optional, separate survival-analysis module.
5. A user-facing dashboard.
6. Model versioning and prediction monitoring.

## Architecture overview

A modular monolith: API → service → repository → database, with a clear request/auth/error-handling pipeline. Full details and a request-flow diagram: [docs/architecture.md](docs/architecture.md).

## Technology stack

- **Python 3.12** (3.11-compatible)
- **FastAPI** + **Uvicorn**
- **Pydantic v2** / **pydantic-settings**
- **SQLAlchemy 2.0** (async, typed ORM) + **asyncpg**
- **Alembic** (migrations)
- **PostgreSQL 16**
- **PyJWT** + **pwdlib[argon2]** (JWT + Argon2 password hashing)
- **pytest** / **pytest-asyncio** / **pytest-cov** / **HTTPX**
- **Ruff** (lint + format) / **mypy** (types)
- **Docker** / **Docker Compose**
- **GitHub Actions** (CI)

## Repository structure

```text
medrisk-ai/
├── app/                  FastAPI application (api, core, db, middleware, models, repositories, schemas, services)
├── alembic/              Database migrations
├── docker/postgres/      PostgreSQL container init script
├── docs/                 Architecture, database, API contract, security, ADRs, learning guide
├── scripts/              wait_for_db.py, check.py, dev.ps1, dev.sh
├── tests/                unit/ and integration/ tests
├── .github/workflows/    CI pipeline
├── compose.yaml          Local PostgreSQL + API stack
├── Dockerfile            API container image
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

> Docker was not available in the environment this Phase 1 build was verified in. The Dockerfile/Compose setup is written to the spec above and reviewed carefully, but `docker build` / `docker compose up` themselves are **not yet verified on this machine** — see the final implementation report for what was and wasn't run.

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
pytest                                          # run the suite
pytest --cov=app --cov-report=term-missing      # with coverage
pytest --cov=app --cov-report=html              # local HTML report (htmlcov/)
```

Integration tests run against a **real PostgreSQL test database** (`TEST_DATABASE_URL`) — never SQLite, never mocks. `tests/conftest.py` forces `ENVIRONMENT=test` before any app module is imported.

## Lint and type checking

```bash
ruff format --check .
ruff check .
mypy app scripts
```

Or run everything CI runs, in order, stopping at the first failure:

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

## Dependencies

Every direct runtime/dev dependency and why it's here is documented inline in [requirements.txt](requirements.txt) and [requirements-dev.txt](requirements-dev.txt).

## Security notes

Password hashing (Argon2), JWT handling, refresh-token rotation, and secret management are documented in [docs/security.md](docs/security.md) and [SECURITY.md](SECURITY.md). No real patient data should ever be used with this project — see the disclaimer at the top of this file.

## Development workflow

- Branch from your default branch, open a PR — CI (`.github/workflows/ci.yml`) runs migrations, `alembic check`, Ruff, mypy, and pytest with coverage.
- Run `python scripts/check.py` locally before pushing.
- See [docs/decisions/ADR-001-backend-architecture.md](docs/decisions/ADR-001-backend-architecture.md) for why the stack looks the way it does, and [docs/learning/phase-01-backend-foundation.md](docs/learning/phase-01-backend-foundation.md) for a guided, Polish-language walkthrough of every concept used.

## Current limitations

- No ML model of any kind is loaded; `predictions/*` inference endpoints always return `501`.
- No file/object storage, no image upload handling.
- `docker build` / `docker compose up` are written and reviewed but unverified on the machine this was built on (Docker not installed there) — see the implementation report.
- Single PostgreSQL instance, no read replicas, no connection-pooling proxy (e.g. PgBouncer) — not needed at this scale yet.

## License

No license has been chosen yet for this portfolio project. All rights reserved by the author until a license is added.
