# Security policy

MedRisk AI is a personal educational/research portfolio project (see the disclaimer in [README.md](README.md)). It is not a medical device, does not knowingly process real patient data, and does not have a dedicated security team or bug-bounty program. This policy is intentionally lightweight.

## Supported scope

Only the code currently on this repository's `main` branch. There is no deployed production instance to report issues against.

## Reporting a vulnerability

If you find a security issue (for example: an authentication bypass, a way to read another user's data, a secret that leaked into logs or version control, or a dependency with a known critical CVE):

1. Do **not** open a public GitHub issue with exploit details.
2. Open a private report instead — via GitHub's "Report a vulnerability" (Security tab on this repository, if enabled) or by contacting the repository owner directly through their GitHub profile.
3. Include: what you found, the steps to reproduce it, and the potential impact.

This is a learning project maintained by one person; please allow reasonable time for a response and a fix.

## What's already documented

- [docs/security.md](docs/security.md) — password hashing, JWT/refresh-token handling, secret management, logging rules, and the no-real-patient-data policy.
- [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md) and [docs/SECURITY_AUDIT.md](docs/SECURITY_AUDIT.md) — the formal threat model and the self-administered audit findings (Phase 8).
- [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md) — the full, currently-accepted security/process limitations list (e.g. per-process rate limiting, no account lockout).
- [docs/decisions/ADR-001-backend-architecture.md](docs/decisions/ADR-001-backend-architecture.md) — why the stack (PyJWT, Argon2 via `pwdlib`, async SQLAlchemy, real-PostgreSQL tests, ...) was chosen.

If your finding matches something already listed as a known limitation, a report is still welcome, but it likely won't be a surprise.
