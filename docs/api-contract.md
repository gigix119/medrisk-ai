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
| 201 | Resource created (registration, a histopathology prediction) |
| 204 | Success, no body (logout) |
| 401 | Missing/invalid/expired/revoked credentials or token |
| 403 | Authenticated but not authorized (reserved; unused) |
| 404 | Resource not found, or a prediction that exists but belongs to another user (never distinguished from "doesn't exist") |
| 409 | Conflict (duplicate email) |
| 413 | Upload exceeds `MAX_UPLOAD_BYTES` |
| 415 | Unsupported image format (not PNG/JPEG) |
| 422 | Request failed validation, or an image failed decode/dimension/format validation |
| 429 | Inference concurrency queue is full — retry after the `Retry-After` header's value |
| 500 | Unexpected server error |
| 501 | Honest placeholder — `/predictions/survival` only; no survival model exists |
| 503 | A required dependency (PostgreSQL, or — when `MODEL_REQUIRED=true` — the histopathology model) is unavailable |
| 504 | Inference exceeded its deadline (`INFERENCE_TIMEOUT_SECONDS`) |

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

No auth, no database access, no model access. Confirms the process is alive.

```json
{ "status": "ok", "service": "medrisk-ai-api", "database": null }
```

## `GET /health/ready`

No auth. Runs `SELECT 1` against PostgreSQL, and additionally requires the histopathology model to be ready when `MODEL_REQUIRED=true`.

- `200` — `{ "status": "ready", "dependencies": { "database": "ready", "histopathology_model": "ready" } }`
- `503` — structured error envelope, `code: "SERVICE_UNAVAILABLE"`, `details.dependencies` showing which dependency failed (`"unreachable"` for the database, `"not_ready"` for the model)

## `GET /health/model`

No auth. Public, non-sensitive model status — never the bundle path or other administration detail.

```json
{
  "status": "ready",
  "model": {
    "model_id": "baseline-cnn-smoke",
    "version": "0.0.1-smoke",
    "architecture": "baseline_cnn",
    "synthetic_only": true,
    "device_type": "cpu",
    "warmup_completed": true
  }
}
```

`model` is `null` and `status` is `"unavailable"` when no model is loaded.

## `GET /api/v1/models/active`

**Auth**: required. Metadata for the currently active histopathology model — the input contract a client needs to know before uploading (`input_contract`), the decision policy (`threshold`, `review_policy`), and provenance (`synthetic_only`, `eligible_for_demo`). Never the bundle filesystem path.

```json
{
  "module": "histopathology",
  "model_id": "baseline-cnn-smoke",
  "model_name": "Baseline CNN (smoke)",
  "version": "0.0.1-smoke",
  "architecture": "baseline_cnn",
  "dataset_name": "synthetic",
  "dataset_mode": "synthetic",
  "synthetic_only": true,
  "eligible_for_demo": false,
  "input_contract": { "input_height": 32, "input_width": 32, "input_channels": 3 },
  "class_names": ["negative", "positive"],
  "positive_class": "positive",
  "threshold": 0.5,
  "review_policy": { "negative_probability_max": 0.3, "positive_probability_min": 0.7 },
  "calibration_enabled": false,
  "activated_at": "2026-06-24T10:10:46.952955Z",
  "disclaimer": "This software is an educational and research portfolio project. ..."
}
```

**Errors**: `503 MODEL_NOT_CONFIGURED` / `503 MODEL_NOT_READY` when no model is active.

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

## `POST /api/v1/predictions/histopathology`

**Auth**: required. **Request**: `multipart/form-data` — `file` (PNG/JPEG, required), `include_explanation` (form boolean, default `false`), `client_reference` (optional, max 100 chars, must not contain patient-identifying information). Full upload contract: [image-input-contract.md](image-input-contract.md).

**Response — `201`**

```json
{
  "prediction_id": "e0f6f899-22cb-4a92-89f8-ff94c9b928d8",
  "module": "histopathology",
  "status": "review_required",
  "decision": "review_required",
  "predicted_class": "positive",
  "raw_probability": 0.5,
  "calibrated_probability": 0.5,
  "predicted_class_probability": 0.5,
  "confidence_score": 0.5,
  "positive_class": "positive",
  "threshold": 0.5,
  "review_policy": { "negative_probability_max": 0.3, "positive_probability_min": 0.7 },
  "input": {
    "sha256": "...", "format": "PNG", "mime_type": "image/png", "size_bytes": 1024,
    "original_width": 32, "original_height": 32, "processed_width": 32, "processed_height": 32
  },
  "model": {
    "model_id": "baseline-cnn-smoke", "model_name": "Baseline CNN (smoke)",
    "version": "0.0.1-smoke", "architecture": "baseline_cnn",
    "synthetic_only": true, "eligible_for_demo": false
  },
  "timings": {
    "validation_ms": 1.2, "preprocessing_ms": 0.8, "inference_ms": 4.1,
    "calibration_ms": 0.01, "explanation_ms": null, "total_ms": 6.3
  },
  "explanation": { "status": "not_requested" },
  "created_at": "2026-06-24T10:10:46.952955Z",
  "disclaimer": "This software is an educational and research portfolio project. ..."
}
```

`status`/`decision` is `"review_required"`, `"completed"` (with `decision` `"negative"`/`"positive"`), or the request fails outright (see errors) — there is no `"pending"`/`"failed"` value the client ever sees synchronously, since this endpoint is fully synchronous: the database row is only ever `pending` for the brief window the model is actually running.

When `include_explanation=true` and it succeeds, `explanation` instead looks like:

```json
{
  "status": "available", "method": "grad_cam", "target_layer": "layer4",
  "mime_type": "image/png", "encoding": "base64", "data": "<base64 PNG>",
  "width": 32, "height": 32, "generation_time_ms": 12.4,
  "disclaimer": "Grad-CAM highlights regions associated with the model output. ..."
}
```

This base64 image is returned **only here, in this immediate response** — it is never persisted and never appears in `/history` or the detail endpoint (`explanation_status` there is a string, not the image).

**Errors**: `400 UPLOAD_EMPTY`, `413 UPLOAD_TOO_LARGE`, `415 UNSUPPORTED_IMAGE_FORMAT`, `422` (`IMAGE_DECODE_FAILED` / `IMAGE_DIMENSIONS_INVALID` / `IMAGE_PIXEL_LIMIT_EXCEEDED` / `IMAGE_MULTIFRAME_NOT_SUPPORTED` / `IMAGE_MIME_MISMATCH`), `429 INFERENCE_QUEUE_FULL`, `503 MODEL_NOT_CONFIGURED` / `MODEL_NOT_READY`, `504 INFERENCE_TIMEOUT`, `500 INFERENCE_FAILED` (generic message; the original error is logged server-side only — see [inference-security.md](inference-security.md)). Full table: [inference-architecture.md](inference-architecture.md#error-codes).

## `POST /api/v1/predictions/survival`

**Auth**: required. **Request**: `{ "notes": "optional, max 1000 chars" }` (a placeholder body — this module has no model in any phase shipped so far).

**Response — `501`**, unconditionally:

```json
{
  "status": "not_implemented",
  "module": "survival",
  "message": "The Phase 1 API foundation is operational, but no survival model is loaded yet. Real inference will be implemented in a later phase. This endpoint must not be used for medical decisions.",
  "disclaimer": "This software is an educational and research portfolio project. ..."
}
```

This is not an error condition from the client's point of view — it is the honest, documented behavior of this endpoint.

## `GET /api/v1/predictions/history`

**Auth**: required. **Query params**: `limit` (1–100, default 20), `offset` (≥0, default 0), and optional filters: `module`, `status`, `decision`, `model_version`, `created_from`, `created_to` (ISO 8601 datetimes).

**Response — `200`**

```json
{ "items": [], "total": 0, "limit": 20, "offset": 0 }
```

Each item is the same flat `PredictionRead` shape returned by the detail endpoint below (see there) — ordered newest-first (`created_at DESC, id DESC`, stable). Always scoped to the calling user — there is no way to request another user's history, and unrecognized/filtered-out items simply don't appear (no error for "no matches").

## `GET /api/v1/predictions/{prediction_id}`

**Auth**: required.

**Response — `200`**

```json
{
  "id": "e0f6f899-22cb-4a92-89f8-ff94c9b928d8",
  "module": "histopathology", "status": "review_required",
  "request_id": "...", "client_reference": null,
  "input_sha256": "...", "input_filename_safe": "patch.png", "input_format": "PNG",
  "input_size_bytes": 1024, "input_width": 32, "input_height": 32,
  "processed_width": 32, "processed_height": 32,
  "model_id": "baseline-cnn-smoke", "model_name": "Baseline CNN (smoke)", "model_version": "0.0.1-smoke",
  "raw_probability": 0.5, "calibrated_probability": 0.5, "confidence_score": 0.5,
  "predicted_class": "positive", "decision": "review_required", "threshold": 0.5,
  "review_lower_bound": 0.3, "review_upper_bound": 0.7,
  "preprocessing_time_ms": 0.8, "inference_time_ms": 4, "calibration_time_ms": 0.01,
  "explanation_time_ms": null, "total_time_ms": 6.3,
  "explanation_requested": false, "explanation_status": "not_requested",
  "error_code": null, "safe_error_message": null,
  "input_metadata": null, "result": { "class_names": ["negative", "positive"], "positive_class": "positive", "architecture": "baseline_cnn" },
  "created_at": "...", "updated_at": "...", "completed_at": "..."
}
```

Never includes the Grad-CAM explanation image, even if one was generated for this prediction — only `explanation_status`.

**Errors**: `404` for a prediction that doesn't exist *or* belongs to another user — these two cases are deliberately indistinguishable, so this endpoint can't be used to probe for the existence of other users' records.
