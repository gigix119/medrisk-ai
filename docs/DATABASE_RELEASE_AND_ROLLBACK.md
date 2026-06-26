# Database release and rollback

This extends [database.md](database.md)'s migration-workflow section with the operational
question that document doesn't answer: when something goes wrong after a release, what is
actually safe to roll back, and what is not? Read [database.md](database.md) first for
schema/migration mechanics.

There has never been a real production release of this project (see
[DEPLOYMENT.md](DEPLOYMENT.md)) — everything below is the documented *procedure*, verified
against the local development/test databases this session, not a record of an incident that
actually happened.

## Four different things called "rollback" — keep them separate

| Rollback type | What it undoes | Tool | Safe by default? |
|---|---|---|---|
| **Application rollback** | Deploying the previous container image/commit | Re-deploy the prior image tag | Usually yes, *if* the database schema hasn't changed between the two versions |
| **Migration rollback** | A specific Alembic schema change | `alembic downgrade <revision>` | **Not always** — see below |
| **Model rollback** | Which `model_deployments` row is "active" | No automated tool today — operator edits `MODEL_BUNDLE_PATH`/restarts (see [model-deployment.md](model-deployment.md)) | Yes — model bundles are immutable files, never mutated in place |
| **Dataset-demo rollback** | Which `datasets` row/version is served | No automated tool today — `scripts/seed_dataset.py` is additive/idempotent, never destructive | Yes — re-running the seed script never deletes an existing dataset version |

These are independent. Rolling back the application container does **not** roll back the
database schema, and vice versa — a release that ships both an app change and a migration
needs both rolled back together, in the right order (migration *down* before the old app
code that doesn't expect the new columns can safely run again, if the migration added
columns the old code never reads; the reverse order if the migration is additive and
backward-compatible — see "Is this migration safe to roll back?" below).

## Standard release procedure (what should happen, in order)

1. Run the full test suite (`python scripts/check.py`, `npm run check` in `frontend/`) on
   the commit being released.
2. Take a database backup (`pg_dump`) before applying any migration against a database with
   real data — even though this project currently only has synthetic/demo data, this step is
   listed because it's the difference between a real incident being recoverable or not.
3. Apply migrations: `alembic upgrade head` against the **target** database (not test,
   not whichever `ENVIRONMENT` happens to be active locally — see
   [database.md](database.md) "Development vs. test database" for why this is easy to get
   wrong).
4. Run `alembic check` to confirm zero drift between the SQLAlchemy models and the migration
   chain.
5. Deploy the new application image.
6. Verify `/health/ready` returns `200` and `/version` reports the expected commit.

## Is this migration safe to roll back?

Not every migration in `alembic/versions/` is safe to `downgrade` blindly. Before running
`alembic downgrade <revision>` against anything other than a disposable local database, read
the migration file's `downgrade()` function and classify it:

- **Reversible, no data loss**: adding a nullable column, adding an index, adding a new
  table that nothing else depends on yet. Safe to downgrade.
- **Reversible, but lossy**: dropping a column that had been storing real data — the
  `upgrade()` direction (drop) destroys data permanently; `downgrade()` re-adds an *empty*
  column, it cannot restore what was in it. Only proceed if a backup exists.
- **Structurally irreversible without manual intervention**: native PostgreSQL `ENUM` types
  are not dropped automatically when their owning table is dropped — the initial migration's
  `downgrade()` has explicit `postgresql.ENUM(...).drop(...)` calls specifically to handle
  this (see [database.md](database.md) "Migration workflow"). A migration that adds a new
  enum value to an *existing* type cannot be cleanly downgraded at all in PostgreSQL (you
  cannot drop a single value from an enum type without recreating it) — if this project ever
  adds such a migration, treat its `downgrade()` with extra suspicion and test it against a
  disposable copy of the real data first.

**This project's current migrations** (`6936f012d734` initial schema,
`01bcb6f81802` model deployments + inference, `c213979b1b21` dataset registry, `4b5e1ce5a386`
research evaluation platform) are all additive (new tables/columns, no destructive
`ALTER`/`DROP` on existing columns) — every one of them falls into the first, safe category.
This was not true by luck; it's the project's own convention (see "Schema discipline" below).

## Schema discipline that keeps rollback boring

- New columns are added nullable (or with a server-side default) so existing rows and
  in-flight requests from the *previous* application version don't break mid-deploy.
- No migration in this repository has ever dropped a column or table that held real
  (non-test) data.
- `4b5e1ce5a386` (Phase 7) added six new tables and one nullable column
  (`datasets.manifest_hash`) — zero changes to any pre-existing column. This is why that
  migration's rollback story is simple: `downgrade()` just drops the six new tables and the
  one new column, and nothing else in the schema references them yet outside the new code
  paths that shipped in the same release.

## Verification performed this session

```bash
alembic current        # confirmed head matches the latest versions file
alembic check           # zero model/migration drift
```

A full `alembic downgrade base && alembic upgrade head` round-trip against the local
development database was **not** re-run this session (it was verified in earlier phases per
[database.md](database.md) "Migration workflow") — re-run it before trusting this document
fully if migrations have changed since the date below.

- Verified: 2026-06-26, against the local development database, commit `88c2b36` plus this
  session's changes (which added no new migration).

## Backup/restore (PostgreSQL, generic)

```bash
# Backup
pg_dump -h <host> -U <user> -d <database> -F custom -f backup.dump

# Restore (to a NEW database - never restore over a live one without a second backup of the
# live one first)
pg_restore -h <host> -U <user> -d <new_database> backup.dump
```

No automated backup schedule exists for this project (there is no deployed instance to
schedule one against — see [DEPLOYMENT.md](DEPLOYMENT.md)). This is a documented gap, not an
implemented control.
