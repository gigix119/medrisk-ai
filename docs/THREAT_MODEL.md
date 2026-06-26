# Threat model

Phase 8 deliverable. This is a practical threat model for the actual MedRisk AI
architecture (FastAPI + SQLAlchemy async + PostgreSQL 16 + JWT auth + a single PyTorch
inference process + a React/Vite frontend) — not a generic checklist. It complements, and
does not replace, [security.md](security.md) (policy/implementation detail) and
[inference-security.md](inference-security.md) (upload-specific threat model, already
detailed and not repeated here).

**Scope note:** this document describes what was reviewed and what controls exist. It is not
a claim of formal certification, a penetration test, or independent audit — see
[SECURITY_AUDIT.md](SECURITY_AUDIT.md) for what was actually verified this session and what
was not.

## Assets

| Asset | Why it matters |
|---|---|
| Source code | Author's portfolio work; integrity matters for trust in the project. |
| Model artifacts (`artifacts/model_registry/`) | Only a synthetic-demonstration bundle exists; tampering could make it falsely appear real or change predictions. |
| Evaluation/experiment artifacts (`artifacts/experiments/`, `research_studies`/`evaluation_runs` tables) | Scientific-integrity backbone (Phase 7) — must reflect real, reproducible runs. |
| Dataset manifests (`datasets`/`dataset_samples` tables, `artifacts/datasets/`) | Currently 100% synthetic; would matter more if a real licensed dataset were ever added. |
| User accounts / password hashes / refresh-token sessions | Standard account-security asset, even though no real PII is intended to ever be stored. |
| JWT signing secret (`JWT_SECRET_KEY`) | Compromise = forge any access/refresh token. |
| Database (PostgreSQL) | Holds everything above. |
| Public reputation of the project | A recruiter-facing portfolio that overstates clinical validity or has an obvious unpatched vulnerability undermines its own purpose. |

## Trust boundaries

```
Browser  --[HTTPS, once deployed; HTTP locally]-->  Frontend (static SPA, Vite build)
Browser  --[Bearer JWT over HTTPS/HTTP]-->           Backend API (FastAPI)
Backend  --[asyncpg, internal network]-->            PostgreSQL
Backend  --[local filesystem, operator-mounted]-->   Model bundle / dataset images
CI (GitHub Actions)  --[no deploy credentials today]--> (no deployment target exists yet)
Public/authenticated user  --[is_superuser check]-->  Administrator-only actions
```

There is currently **no CI→production trust boundary to defend**, because no deployment
target exists (see [DEPLOYMENT.md](DEPLOYMENT.md)). This is listed as a residual item, not
hidden.

## Public / authenticated / admin boundary

Established by Phase 6–8, enforced server-side (not just hidden frontend buttons):

- **Public, no auth**: `/`, `/how-it-works`, `/technology`, `/model`, `/privacy`,
  `/limitations`, `/accessibility`, `/status`, `/login`, `/register`, `GET /health/*`,
  `GET /version`, `GET /docs`/`/redoc`/`/openapi.json`.
- **Authenticated (any registered user)**: everything under `/app/*` in the frontend; in the
  API, prediction history/detail, dataset browsing, controlled sample inference, and all
  research **read** endpoints (studies, audits, evaluations, metrics, confusion matrix,
  errors).
- **Administrator only (`User.is_superuser`, `CurrentSuperuserDep`)**: the three research
  **write** endpoints — `POST .../quality-audit`, `POST .../leakage-audit`, `POST
  /research/evaluations`. Enforced in `app/api/dependencies.py::get_current_superuser`, with
  dedicated authorization tests (`tests/integration/test_research_authorization.py`) proving
  a non-admin gets `403`, not `200`/`201`.

There is intentionally no public upload path, no public dataset/model registration, and no
public account-enumeration surface (login/register return generic messages either way).

## Threats considered

| # | Threat | Affected asset | Attack surface | Current control | Residual risk | Verification | Status |
|---|---|---|---|---|---|---|---|
| 1 | Credential leakage (secrets committed/printed) | JWT secret, DB password | Repo, logs, CI | `.gitignore`/`.dockerignore` exclude `.env*`; `SecretStr` typing hides values in `repr()`; logging never includes auth headers/passwords/tokens (`docs/security.md`) | Git history not rewritten/audited line-by-line this session | Manual grep of tracked files + `.env.example` (this session); no full-history scan | Partially verified |
| 2 | Broken authentication | Accounts, tokens | `/auth/*` | Argon2 hashing, signed JWT with full claim verification, refresh-token rotation+revocation (`docs/security.md`) | No account lockout, no email verification | Existing `tests/integration/test_auth.py` (passing) | Verified-test |
| 3 | Broken authorization / privilege escalation | Research write endpoints | `/api/v1/research/*` POSTs | `CurrentSuperuserDep`, added this phase | None of the other 30+ endpoints needed this distinction (read-only or scoped to the caller's own rows) | `tests/integration/test_research_authorization.py` (4 new tests, all passing) | Verified-test |
| 4 | Anonymous/unauthorized mutation | Datasets, evaluations | All write endpoints | Every mutating endpoint requires `CurrentUserDep` at minimum; admin ones require `CurrentSuperuserDep` | None public-facing | Existing + new integration tests | Verified-test |
| 5 | Insecure direct object reference | Predictions, dataset samples | `GET /predictions/{id}` etc. | History/detail reads scoped to `user_id=current_user.id` (`app/services/prediction.py`) | Not re-audited line-by-line this session beyond spot checks | Existing tests | Verified-test (pre-existing) |
| 6 | SQL injection | Database | All DB access | SQLAlchemy 2.0 typed query builder everywhere; no raw string-interpolated SQL found in `app/` (the only `text()` calls are static `SELECT 1`/`TRUNCATE ... :table-list-is-a-fixed-constant`, never built from request input) | Low | Grep audit this session | Verified-repository |
| 7 | Command injection | Host | None — no endpoint shells out | No `subprocess`/`os.system` call takes request-derived input anywhere in `app/` | Low | Grep audit this session | Verified-repository |
| 8 | Path traversal | Dataset images, model bundle | Dataset sample image endpoint, bundle loader | `resolve_sample_image_path()` and `_ensure_no_symlink_escape()` both resolve + containment-check before any file read (`docs/security.md`, `medrisk_inference/bundle.py`) | Low | Pre-existing tests + this session's read of `bundle.py` | Verified-repository |
| 9 | Malicious file handling (image uploads) | Backend process | Upload endpoints | Decompression-bomb guard, byte/dimension caps, MIME cross-check, EXIF strip (`inference-security.md`) | Out of scope items already documented there | Pre-existing tests | Verified-test (pre-existing) |
| 10 | Unsafe model deserialization | Backend process | Model loading | `torch.load(..., weights_only=True)` (`medrisk_inference/runtime.py:107`), SHA-256 bundle verification, no user-suppliable path | Pinned torch 2.11.0 is well past the `weights_only=True` RCE fix (CVE-2025-32434, fixed in 2.6.0) | `pip-audit` this session; manual code read | Verified-repository |
| 11 | Arbitrary artifact loading | Model registry | Model bundle path | `MODEL_BUNDLE_PATH` is server config only, never request input | None found | Code read | Verified-repository |
| 12 | Denial of service via request volume | Backend process | All endpoints, esp. login/inference/research-write | New in Phase 8: per-process sliding-window rate limiter (`app/core/rate_limit.py`) on login/register/refresh/both inference endpoints/research-write endpoints | **Instance-local only** — no distributed guarantee across multiple worker processes/replicas; other endpoints (history, dataset browsing) remain unlimited | New unit tests (`tests/unit/test_rate_limit.py`) + manual reasoning | Verified-test (logic) / Not-verified (production load) |
| 13 | Oversized image / decompression bomb | Backend process | Upload endpoints | Covered under #9 | — | — | Verified-test (pre-existing) |
| 14 | Excessive inference requests | Backend process, cost | Inference endpoints | Concurrency semaphore (pre-existing) + new rate limiter (#12) | Same as #12 | Same as #12 | Verified-test (logic) |
| 15 | Unrestricted report generation | Backend process | Research write endpoints | Now admin-only (#3) + rate-limited (#12) | None found beyond residual risk in #12 | New tests | Verified-test |
| 16 | CORS misconfiguration | Backend | Browser↔API boundary | Environment-driven allowlist, not wildcard (`app/main.py:167-174`) | Must be set correctly per real deployment target when one exists | Code read | Verified-repository |
| 17 | Token theft (XSS exfiltration) | Access/refresh tokens | Frontend | No `dangerouslySetInnerHTML` anywhere in `frontend/src` (grepped this session); access token in memory only, refresh token in `sessionStorage` only, never `localStorage` | A future dependency with an XSS bug is still a risk to in-memory tokens during the page's lifetime | Grep audit this session | Verified-repository |
| 18 | Secrets embedded in frontend bundle | Frontend build | `dist/` | All `VITE_*` vars audited this session — none are secrets, all are public URLs/branding strings | None found | Grep audit + variable-by-variable review this session | Verified-repository |
| 19 | Stack-trace leakage | Backend responses | Any endpoint | Global exception handlers never return tracebacks; catch-all logs server-side only (`app/main.py:107-120`) | None found | Code read | Verified-repository |
| 20 | Sensitive log leakage | Logs | All requests | No passwords/tokens/auth headers logged (`docs/security.md`) | Request bodies are not logged by default either (not verified this session that no call site ever does so manually — spot-checked, not exhaustive) | Spot check | Partially verified |
| 21 | Dependency compromise / known CVEs | All Python/JS dependencies | Supply chain | `pip-audit` run this session against all three requirements files; `npm audit` run against frontend | One finding: `torch==2.11.0` has `CVE-2025-3000` (medium severity, memory corruption in `torch.jit.script` with list attributes in scripted classes) — **not exploitable here**: this codebase never calls `torch.jit.script` (grepped this session) | Accepted, documented in [SECURITY_AUDIT.md](SECURITY_AUDIT.md) and [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) | `pip-audit`/`npm audit` this session | Verified-test |
| 22 | Tampered model artifact | Model registry | Bundle directory | SHA-256 checksum verification (`verify_bundle`) at every load, not just at registration | An operator with filesystem access could still replace a verified-then-unmounted bundle between checks — accepted, single-operator deployment model | Code read | Verified-repository |
| 23 | Tampered dataset manifest | Dataset registry | `datasets`/`dataset_samples` | Per-sample `checksum_sha256` column; Phase 7's quality audit explicitly flags checksum mismatches as a failed finding | Audit must actually be *run* (admin action) to catch this — not automatic on every read | Existing Phase 7 tests | Verified-test (pre-existing) |
| 24 | Misleading research-result manipulation | Public trust | Research/evaluation display | Metrics are never recomputed by the API (`docs/PHASE_7_PROGRESS.md` decision 7); NaN-safe shaping never silently turns "undefined" into 0; `ResultClassificationBadge` never color-ranks classifications | None found | Pre-existing Phase 7 tests | Verified-test (pre-existing) |
| 25 | Test-data leakage (train/test contamination) | Scientific integrity | Dataset audits | Phase 7 leakage-audit service (exact-checksum cross-split overlap); honestly reports "could not be evaluated" when no subject identifier exists rather than fabricating a pass | Near-duplicate/perceptual-hash and subject-level leakage detection remain unimplemented (documented limitation, not hidden) | Existing Phase 7 tests | Verified-test (pre-existing) |
| 26 | Accidental public exposure of synthetic results as real | Public trust | Landing page, model/dataset cards | Every model/dataset/evaluation surface already labels `synthetic_only`/`is_synthetic`/`result_classification` explicitly; landing page disclaimer; `/model` page states predictions "have no medical meaning whatsoever" | None found | Frontend audit this session (Explore agent) | Verified-repository |

## What this threat model does not cover

- No formal penetration test was performed (see [SECURITY_AUDIT.md](SECURITY_AUDIT.md) for
  the precise distinction).
- No full Git history secret scan (only the current working tree and tracked files were
  checked).
- No load testing of the rate limiter under real concurrent traffic.
- No review of GitHub Actions' own supply chain (pinned action versions were not
  individually re-audited beyond confirming `@v4`/`@v5` major-version pins are used).
- No third-party dependency was manually re-audited beyond what `pip-audit`/`npm audit`
  cover; transitive dependencies not in either tool's database are out of scope.
