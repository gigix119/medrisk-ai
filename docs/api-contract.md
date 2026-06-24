# API contract

Base URL (local dev): `http://127.0.0.1:8000`. All business endpoints are versioned under `/api/v1`; health and root endpoints are not.

Interactive, always-up-to-date documentation: `/docs` (Swagger UI) and `/redoc`. This file is a human-readable summary of the same contract.

## Conventions

- All request/response bodies are JSON, except `POST /api/v1/auth/login`, which uses `application/x-www-form-urlencoded` (OAuth2 password-grant form, so Swagger UI's "Authorize" button and standard OAuth2 tooling work against it).
- All error responses use the same envelope:

  ```json
  {
    "error": {
      "code": "AUTH_INVALID_CREDENTIALS",
      "message": "Invalid email or password.",
      "details": null,
      "request_id": "9cd1c3e1824548caa292f092dcb0d803"
    }
  }
  ```
- Authenticated endpoints require `Authorization: Bearer <access_token>`.
- Pagination responses always have the shape `{"items": [...], "total": N, "limit": N, "offset": N}`.

## Status codes used

| Code | Meaning here |
|---|---|
| 200 | Success |
| 201 | Resource created (registration) |
| 204 | Success, no body (logout) |
| 401 | Missing/invalid/expired/revoked credentials or token |
| 403 | Authenticated but not authorized (reserved; unused in Phase 1) |
| 404 | Resource not found (reserved; unused in Phase 1) |
| 409 | Conflict (duplicate email) |
| 422 | Request failed validation |
| 500 | Unexpected server error |
| 501 | Honest placeholder — endpoint exists, no model is loaded |
| 503 | A required dependency (PostgreSQL) is unavailable |

## `GET /`

No auth. Returns service identification and the medical disclaimer.

```json
{
  "name": "MedRisk AI",
  "version": "0.1.0",
  "environment": "development",
  "docs_url": "/docs",
  "disclaimer": "This software is an educational and research portfolio project. ..."
}
```

## `GET /health/live`

No auth, no database access. Confirms the process is alive.

```json
{ "status": "ok", "service": "medrisk-ai-api", "database": null }
```

## `GET /health/ready`

No auth. Runs `SELECT 1` against PostgreSQL.

- `200` — `{ "status": "ok", "service": "medrisk-ai-api", "database": "ok" }`
- `503` — structured error envelope, `code: "SERVICE_UNAVAILABLE"`

## `POST /api/v1/auth/register`

**Request**

```json
{ "email": "user@example.com", "password": "a-long-secure-password", "full_name": "Example User" }
```

`password`: 12–128 characters. `email`: normalized to lowercase server-side.

**Response — `201`**

```json
{
  "id": "e0f6f899-22cb-4a92-89f8-ff94c9b928d8",
  "email": "user@example.com",
  "full_name": "Example User",
  "is_active": true,
  "is_superuser": false,
  "created_at": "2026-06-24T10:10:46.952955Z",
  "updated_at": "2026-06-24T10:10:46.952955Z"
}
```

Never includes `hashed_password`.

**Errors**: `409 CONFLICT` (email already registered), `422` (invalid email, password too short/long).

## `POST /api/v1/auth/login`

**Request** (`application/x-www-form-urlencoded`, OAuth2 password grant): `username` (the email), `password`.

**Response — `200`**

```json
{
  "access_token": "<jwt>",
  "refresh_token": "<jwt>",
  "token_type": "bearer",
  "expires_in": 900
}
```

**Errors**: `401 AUTHENTICATION_FAILED` with the exact same message ("Invalid email or password.") for a wrong password, an unknown email, *and* an inactive user — the API never reveals which case occurred.

## `POST /api/v1/auth/refresh`

**Request**

```json
{ "refresh_token": "<jwt>" }
```

**Response — `200`**: same shape as login — a brand-new access+refresh pair. The submitted refresh token is revoked as part of this call (rotation); presenting it again fails.

**Errors**: `401 AUTHENTICATION_FAILED` (malformed/unknown/wrong-type token, or the owning user is no longer active), `401 TOKEN_EXPIRED`, `401 TOKEN_REVOKED` (the token was already used or logged out).

## `POST /api/v1/auth/logout`

**Request**

```json
{ "refresh_token": "<jwt>" }
```

**Response — `204`**, no body. Idempotent: logging out twice, or logging out with an already-invalid token, still returns `204`.

## `GET /api/v1/users/me`

**Auth**: required (access token).

**Response — `200`**

```json
{
  "id": "e0f6f899-22cb-4a92-89f8-ff94c9b928d8",
  "email": "user@example.com",
  "full_name": "Example User",
  "is_active": true,
  "is_superuser": false,
  "created_at": "2026-06-24T10:10:46.952955Z",
  "updated_at": "2026-06-24T10:10:46.952955Z"
}
```

**Errors**: `401` (no token, malformed token, a refresh token used where an access token is required, or the user is no longer active).

## `GET /api/v1/predictions/history`

**Auth**: required. **Query params**: `limit` (1–100, default 20), `offset` (≥0, default 0).

**Response — `200`**

```json
{ "items": [], "total": 0, "limit": 20, "offset": 0 }
```

Each item (once any exist) has the shape:

```json
{
  "id": "...", "module": "histopathology", "status": "pending",
  "input_metadata": null, "result": null, "confidence_score": null,
  "model_name": null, "model_version": null, "inference_time_ms": null,
  "error_code": null, "created_at": "...", "updated_at": "..."
}
```

Always scoped to the calling user — there is no way to request another user's history.

## `POST /api/v1/predictions/histopathology` / `POST /api/v1/predictions/survival`

**Auth**: required. **Request**: `{ "notes": "optional, max 1000 chars" }` (a placeholder body; Phase 1 does not accept image data).

**Response — `501`** for both, unconditionally:

```json
{
  "status": "not_implemented",
  "module": "histopathology",
  "message": "The Phase 1 API foundation is operational, but no histopathology model is loaded yet. Real inference will be implemented in a later phase. This endpoint must not be used for medical decisions.",
  "disclaimer": "This software is an educational and research portfolio project. ..."
}
```

This is not an error condition from the client's point of view — it is the honest, documented behavior of this endpoint in Phase 1.
