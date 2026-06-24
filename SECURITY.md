# Security policy

MedRisk AI is a personal educational/research portfolio project (see the disclaimer in [README.md](README.md)). It is not a medical device, does not knowingly process real patient data, and does not have a dedicated security team or bug-bounty program. This policy is intentionally lightweight.

## Supported scope

Only the code in this repository, in its current Phase 1 (backend foundation) form. There is no deployed production instance to report issues against.

## Reporting a vulnerability

If you find a security issue (for example: an authentication bypass, a way to read another user's data, a secret that leaked into logs or version control, or a dependency with a known critical CVE):

1. Do **not** open a public GitHub issue with exploit details.
2. Open a private report instead — via GitHub's "Report a vulnerability" (Security tab on this repository, if enabled) or by contacting the repository owner directly through their GitHub profile.
3. Include: what you found, the steps to reproduce it, and the potential impact.

This is a learning project maintained by one person; please allow reasonable time for a response and a fix.

## What's already documented

- [docs/security.md](docs/security.md) — password hashing, JWT/refresh-token handling, secret management, logging rules, the no-real-patient-data policy, and currently known Phase 1 limitations (e.g. no login rate limiting yet).
- [docs/decisions/ADR-001-backend-architecture.md](docs/decisions/ADR-001-backend-architecture.md) — why the stack (PyJWT, Argon2 via `pwdlib`, async SQLAlchemy, real-PostgreSQL tests, ...) was chosen.

If your finding matches something already listed as a known limitation, a report is still welcome, but it likely won't be a surprise.
