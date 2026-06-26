# Database

PostgreSQL 16. Schema is managed entirely through Alembic migrations (`alembic/versions/`) — the application never creates or alters tables at startup.

## Conventions

- **Primary keys**: client-generated UUID4 (`uuid.uuid4()`, Python-side default), typed as SQLAlchemy's generic `Uuid`, stored as native PostgreSQL `uuid`.
- **Timestamps**: `DateTime(timezone=True)` everywhere — always timezone-aware, set by the database (`server_default=func.now()`), never by application code.
- **Enums**: native PostgreSQL `ENUM` types (`prediction_module`, `prediction_status`, `model_deployment_status`), stored as their lowercase string values (`histopathology`, not `HISTOPATHOLOGY`).
- **JSON**: `JSONB`, used only for genuinely semi-structured fields (`input_metadata`, `result`).

## Tables

### `users`

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` | Primary key |
| `email` | `varchar(255)` | Unique, indexed, normalized to lowercase before it ever reaches this table |
| `hashed_password` | `varchar(255)` | Argon2 hash — never plaintext, never returned by any API schema |
| `full_name` | `varchar(255)` | |
| `is_active` | `boolean` | Default `true`. Inactive users cannot log in or refresh, even with a valid token |
| `is_superuser` | `boolean` | Default `false`. Enforced since Phase 8 by `CurrentSuperuserDep` (`app/api/dependencies.py`) on the three research write endpoints — see [security.md](security.md) "Authorization (Phase 8)". Set via `scripts/promote_superuser.py`, the only way to grant it (no API does) |
| `created_at`, `updated_at` | `timestamptz` | |

### `refresh_token_sessions`

Tracks refresh-token issuance so tokens can be rotated and revoked server-side — a JWT's signature alone can't be "revoked" before it expires, so revocation has to live in the database.

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` | Primary key |
| `user_id` | `uuid` | FK → `users.id`, `ON DELETE CASCADE` |
| `jti` | `varchar(64)` | Unique, indexed. The token's JWT ID claim — how a presented token is looked up |
| `token_hash` | `varchar(64)` | SHA-256 hex digest of the raw refresh token. **The raw token is never stored** |
| `expires_at` | `timestamptz` | Mirrors the JWT's own `exp` claim |
| `revoked_at` | `timestamptz`, nullable | Set on logout or on rotation (the old session is revoked when a new one is issued) |
| `replaced_by_jti` | `varchar(64)`, nullable | Points to the session that replaced this one, for audit purposes |
| `created_at` | `timestamptz` | |
| `last_used_at` | `timestamptz`, nullable | Updated when the token is presented for a refresh |
| `user_agent` | `varchar(512)`, nullable | Stored for auditing only — never required to match |
| `ip_address` | `inet`, nullable | Stored for auditing only — never required to match |

A session is **active** when `revoked_at IS NULL` and the underlying JWT hasn't expired; **revoked** when `revoked_at IS NOT NULL` (via logout or rotation); **expired** when the JWT's own `exp` has passed (checked by JWT verification, not a separate database check — the two are always set to the same value at issuance, so a separate database-side expiry check would be redundant).

### `predictions`

Phase 1 established this schema with no real inference (the endpoints returned `501` without touching the table). Phase 3 wires up real histopathology inference and extends the table with audit columns — see [app/models/prediction.py](../app/models/prediction.py) for the exhaustive column list; the groups are:

| Column group | Examples | Notes |
|---|---|---|
| Identity (Phase 1) | `id`, `user_id`, `module`, `status`, `created_at`, `updated_at` | `user_id` indexed, plus a composite `(user_id, created_at)` index for the history query |
| Request audit (Phase 3) | `request_id`, `client_reference` | `client_reference` is free-text and must never contain patient-identifying information — the API cannot enforce that for a free-text field, only document it |
| Input technical metadata (Phase 3) | `input_sha256`, `input_filename_safe`, `input_mime_type`, `input_format`, `input_size_bytes`, `input_width`/`height`, `processed_width`/`height` | **Never the raw image itself** — see [image-input-contract.md](image-input-contract.md) |
| Model identity (Phase 3) | `model_deployment_id` (FK → `model_deployments.id`, `ON DELETE SET NULL`, nullable), `model_id`, `model_name`, `model_version`, `model_bundle_sha256` | The FK is nullable because history predates the `model_deployments` table existing at all |
| Decision pipeline output (Phase 3) | `raw_probability`, `calibrated_probability`, `confidence_score`, `predicted_class`, `decision`, `threshold`, `review_lower_bound`/`upper_bound` | See [inference-architecture.md](inference-architecture.md#the-decision-pipeline) |
| Timings (Phase 3) | `preprocessing_time_ms`, `inference_time_ms`, `calibration_time_ms`, `explanation_time_ms`, `total_time_ms` | |
| Outcome (Phase 1+3) | `input_metadata`, `result` (`jsonb`, nullable), `explanation_requested`, `explanation_status`, `error_code`, `safe_error_message`, `completed_at` | `result` holds only non-identifying summary fields (class names, architecture) — never the Grad-CAM image, which has no column at all |

**No raw patient-identifying information, and no raw image bytes, are ever stored here** — no names, no PESEL/medical-record numbers, no addresses, no pixel data. See [security.md](security.md) and [inference-security.md](inference-security.md).

### `model_deployments`

One row per model-load *attempt* (Phase 3) — a durable audit trail of which model was active when, not just a pointer to the current one. See [model-deployment.md](model-deployment.md) for the full lifecycle.

| Column | Type | Notes |
|---|---|---|
| `id`, `created_at`, `updated_at` | | |
| `module` | `prediction_module` enum | Shared enum with `predictions.module` |
| `model_id`, `model_name`, `model_version`, `architecture`, `dataset_name`, `dataset_mode` | `varchar` | From the bundle's manifest |
| `bundle_path` | `varchar(1024)` | **Internal administration only — never returned by any API response** |
| `bundle_sha256` | `varchar(64)` | |
| `synthetic_only`, `eligible_for_demo` | `boolean` | Mirrored from the manifest so deployment history doesn't require re-reading old bundles from disk |
| `device` | `varchar(20)` | What `MODEL_DEVICE` resolved to |
| `status` | `model_deployment_status` enum | `loading` \| `active` \| `inactive` \| `failed` |
| `loaded_at`, `activated_at`, `deactivated_at` | `timestamptz`, nullable | Lifecycle timestamps |
| `warmup_completed`, `warmup_duration_ms` | | |
| `failure_code` | `varchar(100)`, nullable | An `error_code`, never a raw stack trace |
| `metadata_json` | `jsonb`, nullable | Reserved for future use; currently unwritten |

Rows are never deleted when a new model activates — only superseded (`status` flips to `inactive`, `deactivated_at` stamped).

## Migration workflow

```bash
alembic revision --autogenerate -m "describe the change"   # generate
# review the generated file by hand - autogenerate is a draft, not a guarantee
alembic upgrade head                                         # apply
alembic current                                              # verify
alembic check                                                 # confirm no drift between models and the last migration
```

Autogenerated migrations are reviewed before being trusted — in particular, **native PostgreSQL `ENUM` types are not dropped automatically** when the table that used them is dropped (see the explicit `postgresql.ENUM(...).drop(...)` calls at the end of `downgrade()` in the initial migration). Without that, a `downgrade` followed by another `upgrade` would fail with "type already exists."

Tested locally with a full round-trip:

```bash
alembic downgrade base
alembic upgrade head
```

This is safe against a local development database whose contents you can afford to lose. It is never run against an unknown or shared database.

## Development vs. test database

Two databases, same PostgreSQL instance: `medrisk` (development) and `medrisk_test` (integration tests). Which one the application/Alembic targets is decided by `ENVIRONMENT` (`app/db/session.py:get_database_url`) — `ENVIRONMENT=test` always resolves to `TEST_DATABASE_URL`. `tests/conftest.py` forces `ENVIRONMENT=test` before any app module is imported, so running `pytest` can never accidentally touch development data. Integration tests truncate all application tables after each test (`tests/integration/conftest.py`) rather than relying on a rolled-back transaction, because the app under test and the test itself use independent `AsyncSession`s (and therefore independent transactions) talking to the same real database.

## Why raw medical information is not stored

This is a portfolio/research project, not a clinical system: it has no legal basis, security audit, or infrastructure appropriate for handling real patient data. The `predictions` table's `input_metadata`/`result` fields are typed as open-ended JSON specifically so model-relevant metadata (e.g. preprocessing parameters, class names) can be attached without ever needing a column that could hold a name, a medical record number, or any other directly identifying field. Phase 3's image-specific columns (`input_sha256`, `input_width`/`height`, ...) are deliberately narrow, typed columns rather than another JSON blob — specifically so it stays obvious, at the schema level, that there is no column wide enough to hold a raw image. All future demonstrations use public, synthetic, or properly anonymized datasets.
