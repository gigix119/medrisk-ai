# Security

## Password hashing

Passwords are hashed with **Argon2** via `pwdlib` (`app/core/security.py`). Never `passlib`, never a reversible scheme. The plaintext password is held in memory only long enough to hash it during registration or to verify it during login — it is never logged and never persisted. `pwdlib.PasswordHash([Argon2Hasher()])` is constructed explicitly (rather than relying on `PasswordHash.recommended()`) so the choice of algorithm is visible in the code and doesn't silently change if the library's "recommended" default ever does.

Registration enforces a 12–128 character password length and otherwise avoids complex composition rules (mandatory symbols/uppercase) — length contributes far more to actual brute-force resistance than composition rules do, and composition rules mostly push users toward predictable patterns.

## JWT token handling

Both access and refresh tokens are signed JWTs (PyJWT, HS256) carrying `sub`, `type` (`access`/`refresh`), `iat`, `exp`, `iss`, `aud`, and `jti`. `app/core/security.py:decode_token` verifies, on every single call: signature, expiry, issuer, audience, presence of all required claims, and — after PyJWT's own checks — that `type` matches what the caller expects (so a refresh token can never be used as an access token, and vice versa).

- **Access tokens** are short-lived (`JWT_ACCESS_TOKEN_EXPIRE_MINUTES`, default 15) and stateless — there is no server-side record of an issued access token. Revoking one before its natural expiry is not currently possible; this is an accepted Phase 1 limitation given how short the lifetime is.
- **Refresh tokens** are long-lived (`JWT_REFRESH_TOKEN_EXPIRE_DAYS`, default 7) and **are** tracked server-side, in `refresh_token_sessions`, specifically so they can be revoked and rotated.

## Refresh-token rotation

Every successful `/auth/refresh` call:

1. Verifies the presented JWT (signature/expiry/issuer/audience/type).
2. Looks up the session by `jti`, and verifies the stored SHA-256 fingerprint of the token matches the one presented (`hmac.compare_digest` — constant-time, so comparison timing can't leak how much of the hash matched).
3. Rejects if that session is already `revoked_at IS NOT NULL`.
4. Revokes the old session and issues a brand-new access+refresh pair in the same database transaction.

This means a refresh token is single-use: once rotated, presenting the old one again is treated as `TOKEN_REVOKED`, not silently accepted. If an attacker ever captured a refresh token and used it, the legitimate user's next refresh attempt with their own (now-superseded) copy would fail loudly — a real-world deployment would want to alert on this, though Phase 1 only rejects it.

## Secret management

- `JWT_SECRET_KEY` has **no working default**. `app/core/config.py` raises a validation error at startup if it's missing, empty, a known-insecure placeholder (e.g. `"changeme"`), or shorter than 32 characters — for every environment except `test`, where only "non-empty" is required (so CI can use a fixed, public, harmless value).
- Secrets live in `.env`, which is git-ignored and must never be committed. `.env.example` documents every variable with a non-secret placeholder.
- `POSTGRES_PASSWORD` and `JWT_SECRET_KEY` are typed as Pydantic `SecretStr` — their `repr()` is `**********`, so an accidental `print(settings)` or stray log line doesn't leak them.

## Logging

`app/core/logging.py` configures the standard library `logging` module only. Every call site is expected to never log: plaintext passwords, password hashes, JWTs (access or refresh), the `Authorization` header, raw refresh tokens, or database credentials. Health/readiness checks, request logs, and the global exception handler log a request ID and an error *type*, not raw exception payloads that might contain sensitive input.

## Histopathology inference (Phase 3)

`POST /api/v1/predictions/histopathology` performs real model inference against an uploaded image — see [inference-security.md](inference-security.md) for the full threat model (decompression bombs, EXIF/metadata stripping, MIME spoofing, error-message safety, synthetic-model guardrails) and [image-input-contract.md](image-input-contract.md) for the upload validation contract. The `/survival` endpoint remains an honest `501` placeholder, same as Phase 1.

## No real patient data

This is an educational/research portfolio project, not a system with the legal basis, audit trail, or infrastructure hardening required to handle real patient data:

- No real patient data should ever be uploaded to or processed by this system.
- No names, PESEL numbers, addresses, medical record numbers, or other directly identifying clinical information should be stored anywhere, including in the open-ended `predictions.input_metadata`/`result` JSONB columns or the free-text `client_reference` field.
- All future demonstrations must use public, synthetic, or properly anonymized data. The one model bundle shipped in this repository is synthetic-only and has no medical meaning whatsoever (see [model-deployment.md](model-deployment.md)).
- The application is not a medical device. Results — including the `/survival` placeholder's `501` response and the histopathology endpoint's real-but-synthetic-model output — must never be used for diagnosis, treatment decisions, or emergency medical guidance. Every prediction response carries this disclaimer explicitly.
- The raw uploaded image is never persisted, on disk or in the database, under any circumstance — see [image-input-contract.md](image-input-contract.md) "What is never persisted or returned."

## Responsible reporting

This is a personal portfolio project without a dedicated security team or bug-bounty program. See [SECURITY.md](../SECURITY.md) at the repository root for how to report a concern.

## Known Phase 1 limitations

- No rate limiting on `/auth/login` or `/auth/register` (brute-force/enumeration mitigation beyond the generic error message is not yet implemented).
- No account lockout after repeated failed login attempts.
- No email verification step on registration.
- No CSRF protection — not currently needed because the API is token-based (Bearer auth, not cookies), but would need revisiting if cookie-based auth were ever added.
- No revocation mechanism for access tokens before their natural (short) expiry.
- No structured/JSON logging output yet (human-readable only) — the logging module is structured internally so this can change without touching call sites.
