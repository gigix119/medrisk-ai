# Security audit — Phase 8

**This is a self-administered code/configuration review, not a penetration test and not an
independent third-party audit.** No external party reviewed this. The distinction matters: a
review like this one finds the classes of issue the reviewer thought to look for; it does not
find what a determined, time-unlimited attacker would.

## Audit scope

- Date: 2026-06-26.
- Scope: the `medrisk-ai` repository at commit `88c2b36` and the changes made on top of it in
  this Phase 8 session (rate limiting, admin authorization, `/version`, CI security jobs).
- In scope: backend (`app/`, `medrisk_inference/`, `medrisk_research/`), frontend
  (`frontend/src/`), Docker/Compose files, CI workflow, dependency manifests, documentation
  for accuracy/overclaiming.
- Out of scope (explicitly, not silently skipped): no deployed instance exists yet, so no
  network-level scan, no TLS configuration review, no real-traffic load test, and no
  CSP/security-header verification against a live response (there is nothing to point a
  header scanner at — see [DEPLOYMENT.md](DEPLOYMENT.md)).

## Methods used

1. Manual code review (FastAPI app factory, dependency layer, exception handling, auth
   service, rate limiter, ORM query sites) via direct file reads and targeted `grep`.
2. Four parallel read-only exploration passes (backend security, Docker/CI, frontend
   security/routing, documentation/licensing) cross-checked against the actual source, not
   assumed from naming conventions.
3. `pip-audit` against all three Python requirement files (`requirements.txt`,
   `requirements-inference.txt`, `requirements-ml.txt`).
4. `npm audit` against `frontend/package-lock.json`.
5. Manual secret-pattern grep across tracked files and `.env.example`/`frontend/.env.example`
   (current working tree only — no full Git history scan).
6. The existing automated test suites (334 backend / frontend suite) as a correctness
   safety net for every change made this session.

## Findings

| ID | Finding | Severity | Status before Phase 8 | Remediation | Verification |
|---|---|---|---|---|---|
| F-1 | No rate limiting on login/register/refresh/inference/research-write endpoints | Medium | Open (documented as a known limitation since Phase 1) | Added `app/core/rate_limit.py`, a per-process sliding-window limiter, wired into all six endpoint groups | `tests/unit/test_rate_limit.py` (4 tests); manual code review of every call site |
| F-2 | Any authenticated user (not just an administrator) could trigger a dataset quality/leakage audit or create an evaluation run | Medium | Open | `User.is_superuser` (existing, unused, column) is now enforced via `CurrentSuperuserDep` on the three write endpoints | `tests/integration/test_research_authorization.py` (5 tests: 3 deny-by-default, 1 superuser-allowed, 1 unauthenticated-401) |
| F-3 | No `GET /version` endpoint for safe release metadata | Low | Open | Added, returning app name/version/environment/optional git commit/optional model version — never fabricated, `None` when unavailable | Manual test; covered indirectly by existing health-endpoint test patterns (no dedicated new test added — see "Known gaps" below) |
| F-4 | `torch==2.11.0` (pinned in `requirements-inference.txt`/`requirements-ml.txt`) has a published CVE (`CVE-2025-3000`, medium/CVSS 5.3) | Low (not exploitable here) | Newly discovered this session | **Accepted, not patched.** `CVE-2025-3000` is a memory-corruption issue specific to `torch.jit.script` on scripted classes with list attributes. Grepped the entire repository for `jit.script`/`torch.jit` — zero matches. This codebase never uses TorchScript. No fix version was available from `pip-audit` at audit time; re-check when bumping torch for unrelated reasons. | `pip-audit -r requirements-inference.txt` / `-r requirements-ml.txt`; `grep -r "jit.script\|torch.jit"` (zero matches) |
| F-5 | No CI job runs `pip-audit`/`npm audit`/secret scanning automatically | Low | Open | Added a `security` job to `.github/workflows/ci.yml` (see that file) | First real run happens on the next push/PR — not yet observed in a live GitHub Actions run as of this writing (see "Known gaps") |
| F-6 | No CI `permissions:` block (defaults to the repository's broader default token scope) | Low | Open | Added `permissions: contents: read` at the workflow level | Visual diff of `ci.yml`; not independently verified against a live run |
| F-7 | No formal threat model document | Low (process gap, not a vulnerability) | Open | Added [THREAT_MODEL.md](THREAT_MODEL.md) | N/A (documentation) |
| F-8 | No structured documentation of which dataset/model artifacts are real vs. synthetic and what may be publicly redistributed | Low (process gap) | Open | Added [DATA_AND_MODEL_PROVENANCE.md](DATA_AND_MODEL_PROVENANCE.md) | N/A (documentation) |
| F-9 | `npm audit` reports 2 moderate-severity findings (`js-yaml` quadratic-complexity DoS, via `@redocly/openapi-core`) | Low (not exploitable here) | Newly discovered this session | **Accepted, no action needed.** `@redocly/openapi-core` is a transitive dependency of `openapi-typescript` (`frontend/package.json` devDependency), used only by the local `npm run api:generate` script against this repo's own `openapi.json` — never shipped in the production bundle, never fed untrusted YAML. CI's `npm audit --audit-level=high` already passes (moderate is below the configured threshold) | `npm audit --audit-level=high` (exit 0) |

## What was checked and found already adequate (not re-fixed)

- CORS: environment-driven allowlist, not wildcard.
- JWT: signed, fully-claim-verified, 32-char minimum production secret, refresh-token
  rotation and revocation.
- Exception handling: no stack traces or internal paths ever returned to a client.
- Upload safety: size/dimension/pixel caps, decompression-bomb guard, EXIF stripping, MIME
  cross-check (pre-existing, [inference-security.md](inference-security.md)).
- Model-artifact loading: SHA-256 checksum verification, `weights_only=True` (already past
  the `torch.load` RCE fix), symlink-escape rejection, no user-suppliable bundle path.
- Docker: non-root user in all three images, no secrets baked in, no debug/reload flags,
  healthchecks present.
- Frontend: no `dangerouslySetInnerHTML`, no secrets in any `VITE_*` variable, sound token
  storage (in-memory access token, `sessionStorage` refresh token, comprehensive logout),
  enforced `ProtectedRoute` boundary.
- Public/private route boundary already matched the master prompt's intended model before
  this phase started.

## Known gaps in this audit (not silently omitted)

- **No live CI run observed.** The new `security` job in `ci.yml` was written and locally
  reasoned about, but its first real execution happens on the next push/PR to this branch —
  this document will be wrong if that run surfaces an unexpected failure; check the Actions
  tab before treating F-5/F-6 as fully closed.
- **No dedicated automated test for `GET /version`.** Manually reasoned correct (mirrors the
  existing `/health/model` pattern exactly) but not covered by a new assertion.
- **No full Git history secret scan.** `detect-secrets`/the CI job scan the current working
  tree; an old commit on `main` predating this convention was not individually inspected.
- **No header/CSP verification.** There is no deployed instance to scan response headers
  against (see [DEPLOYMENT.md](DEPLOYMENT.md) — this is an external blocker, not a skipped
  step).
- **No load/concurrency test of the new rate limiter under real traffic.** Logic is unit
  tested deterministically (`now` is injected); real-clock, real-concurrency behavior is not.
- **Authorization review was endpoint-by-endpoint, not exhaustive fuzzing.** Every endpoint
  in `app/api/v1/endpoints/*.py` was read and classified (public/authenticated/admin) but no
  automated tool swept for missed cases beyond the new tests for the three changed endpoints.

## Residual risk summary

Nothing found in this audit is rated Critical or High. The two Medium findings (F-1, F-2)
were both remediated this session with passing tests. The one newly-discovered dependency
finding (F-4) has no exploitable code path in this repository and is accepted with
justification. The largest remaining category of risk is operational, not code-level: this
project has never been deployed publicly, so none of its network-facing controls (CORS
origin list, CSP headers, TLS) have been exercised against real traffic — see
[DEPLOYMENT.md](DEPLOYMENT.md) and [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md).
