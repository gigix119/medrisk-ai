# Project scope — Phase 1: Backend Foundation

## What Phase 1 does

Phase 1 builds a production-conscious backend foundation for MedRisk AI:

- A modular-monolith FastAPI application (`app/api`, `app/core`, `app/db`, `app/middleware`, `app/models`, `app/repositories`, `app/schemas`, `app/services`).
- Async PostgreSQL access via SQLAlchemy 2.0 + asyncpg, with one `AsyncSession` per request — never a shared global session.
- Schema-managed (Alembic) tables for users, refresh-token sessions, and predictions.
- JWT authentication: registration, login, access + refresh tokens, refresh-token rotation with reuse detection, and logout/revocation.
- Argon2 password hashing (via `pwdlib`), never `passlib`, never plaintext, never a reversible encryption scheme.
- A structured error-response format, request-ID propagation, and centralized exception handling.
- Liveness/readiness health endpoints.
- Honest placeholder prediction endpoints that return `501 Not Implemented` instead of fabricated results.
- A real-PostgreSQL automated test suite (unit + integration), Ruff/mypy quality gates, Docker/Compose, and CI.

## What Phase 1 does not do

- No CNN, no transfer learning, no Grad-CAM, no scikit-learn models.
- No dataset downloading (PCam, TCGA, or otherwise).
- No survival-analysis statistics.
- No frontend, no React, no Streamlit.
- No file/object storage or image upload handling.
- No real medical inference of any kind — `predictions/histopathology` and `predictions/survival` always return `501` and say so explicitly.

## Why no real ML prediction exists yet

Building the inference layer before the foundation is solid would mean building it on sand: no reliable auth, no migration story, no tests, no consistent error handling. Phase 1 deliberately front-loads the unglamorous backend-engineering work — config, security, persistence, testing, CI — so that when a real model is introduced in a later phase, it plugs into a system that already knows how to authenticate users, store results safely, and fail predictably.

Equally important: this project must never present a fabricated result as if it were a genuine prediction, even temporarily "as a placeholder." A `501` response that says "no model is loaded" is safe. A random or hardcoded "87% probability of malignancy" is not — even in a portfolio project, even obviously fake to the person reading the code, because copy-pasted or screenshotted output loses that context.

## Research / educational positioning

MedRisk AI is a personal portfolio and learning project. It demonstrates backend engineering practice (FastAPI, async SQLAlchemy, JWT auth, testing, CI/CD) in a domain (oncology imaging) chosen for its complexity and educational interest — not because the software is intended for clinical use. All future demonstrations will use public, synthetic, or properly anonymized data. See [security.md](security.md) for the data-handling policy in detail.

## Future phases (high level, not implemented yet)

1. **Histopathology classification** — a CNN/transfer-learning model, trained on a public dataset (e.g. PatchCamelyon), served through a real version of the `predictions/histopathology` endpoint.
2. **Grad-CAM** — visual explanations overlaid on input images, so predictions are inspectable rather than opaque.
3. **Model quality and error analysis** — confusion matrices, calibration, failure-case review.
4. **Survival analysis** — a separate, optional module, statistically distinct from the classification work.
5. **User dashboard** — a frontend consuming this API.
6. **Model versioning and prediction monitoring** — tracking which model version produced which result over time, and watching for drift.

Each future phase builds on the contracts established here (the `Prediction` model's `module`/`status`/`result`/`model_name`/`model_version` fields already anticipate this) without requiring a rewrite of the auth, persistence, or error-handling foundation.
