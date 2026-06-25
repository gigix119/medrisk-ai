# Development workflow

This is a single-maintainer portfolio project; the workflow below is intentionally lightweight, but mirrors what CI enforces so nothing that fails CI should be a surprise.

## One-time setup

See the README's [Windows](../README.md#setup--windows-powershell) or [Linux/macOS](../README.md#setup--linuxmacos) setup sections: create `.venv`, install `requirements-dev.txt`, copy `.env.example` to `.env`, generate a real `JWT_SECRET_KEY`, and make sure PostgreSQL is reachable with both the `medrisk` and `medrisk_test` databases created.

## Day-to-day loop

```bash
# 1. Make a change in app/ (and a matching test in tests/)
# 2. If you changed a model, create + review + apply a migration:
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
alembic check

# 3. Run the full local quality gate before considering the change done:
python scripts/check.py
```

`scripts/check.py` runs, in this order, stopping at the first failure: `ruff format --check`, `ruff check`, `mypy app scripts medrisk_inference`, `pytest --cov=app --cov=medrisk_inference --cov-report=term-missing`. This is the same sequence `.github/workflows/ci.yml` runs (plus the migration steps, which only make sense in a job that provisions a fresh database). `medrisk_ml` has its own equivalent gate, run by CI's separate `ml` job — see [ml-architecture.md](ml-architecture.md).

## Running just one thing

```bash
ruff format .                          # auto-fix formatting
ruff check --fix .                     # auto-fix the lintable issues
mypy app scripts medrisk_inference      # types only
pytest tests/unit                       # fast, no database
pytest tests/integration -v             # against the real test database
pytest -k test_login_with_wrong_password_returns_401   # one test by name
```

## Branching and PRs

There's no fixed branch-naming convention enforced by tooling here — use whatever is descriptive. Open a pull request against the default branch; `.github/workflows/ci.yml` runs automatically and must pass (migrations + `alembic check` + Ruff + mypy + pytest with coverage) before merging.

## Adding a dependency

1. Add it to `requirements.txt` (runtime) or `requirements-dev.txt` (dev/test/lint/type-check tooling only).
2. Install it (`pip install -r requirements-dev.txt`), confirm `scripts/check.py` still passes.
3. Pin the exact installed version (`pip freeze` to find it) and add a one-line comment explaining *why* the dependency exists, next to the others at the top of the requirements file.
4. If it's a new direct dependency, mention it in the README's [Dependencies](../README.md#dependencies) section.

## Writing tests

- A test that doesn't touch the database or HTTP layer belongs in `tests/unit/`.
- A test that exercises a real endpoint and/or the real test database belongs in `tests/integration/` and can use the `client`, `db_session`, `registered_user`, and `auth_tokens` fixtures from `tests/integration/conftest.py`.
- Integration tests run against `medrisk_test`, never `medrisk` — see [database.md](database.md#development-vs-test-database) for how that's enforced.
- Don't add `# type: ignore` or `# noqa` to make a check pass without understanding what it was flagging — fix the underlying issue, or leave a comment explaining the specific, narrow reason the suppression is correct.

## Useful local commands

```bash
python -m uvicorn app.main:app --reload      # run the API with autoreload
python scripts/dev.ps1   # or scripts/dev.sh   # same thing, with a friendlier error if .venv is missing
python -m scripts.wait_for_db                 # poll until PostgreSQL is reachable (used by Docker Compose)
alembic history                                # list all migrations
alembic downgrade -1                           # roll back one migration (local dev DB only)
```
