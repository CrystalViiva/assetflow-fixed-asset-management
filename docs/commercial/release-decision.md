# Commercial transformation release decision

**Decision at this checkout: NOT READY — ENGINEERING BLOCKERS REMAIN.** This is a repository-only validation. No public deployment, staging account, operational email delivery, production backup restore, billing sandbox, or live provider credentials are present.

## C1–C6 status

| Milestone | Implemented | Validated | Status and exact remaining work |
|---|---|---|---|
| C1 — Commercial readiness audit | Source-level audit, architecture/data flow, functionality matrix, blocker register, architecture decision record. | Cross-checked against the source and historical F16 evidence. | Complete as an audit; it does not assert product readiness. |
| C2 — Managed onboarding and identity | Production SMTP settings foundation; suspended organizations now reject existing JWT access; account lifecycle findings and customer/admin guides. Existing tenant user directory remains. | Focused authentication tests cover active/suspended organizations; request identity tests pass. | Partial. No operator-only provisioning command/API, explicit operator role, user invitation/acceptance, password reset/change, verified signup, backend throttling, or frontend flows. |
| C3 — Security and operations | Production secret/host checks, HSTS/security headers, DB readiness, correlation IDs, shorter web/proxy timeouts, encrypted backup/verification scripts, runbooks and threat model. | Django system check, focused Python tests, Ruff; shell script syntax validation. | Partial. No full PostgreSQL suite or disposable restore drill; no monitoring/alerts, provider-level durable storage, auth rate limit, MFA, or measured recovery evidence. |
| C4 — Hosted deployment | Existing production Compose reviewed and tightened; explicit email/origin/base URL configuration; current hosting options compared. | Docker Compose configuration parses; frontend Django-mode build passes. | Partial / blocked. Docker Engine is unavailable, no staging, cloud account, DNS/TLS, external object storage, email provider, or real hosted smoke test. |
| C5 — Website and sales enablement | Existing landing page/product copy reviewed; inaccurate scaffold metadata corrected; customer guides, demo/discovery/pilot/pricing, legal review drafts added. | Existing frontend suite and production build pass. | Partial. No functioning persisted contact/demo request, complete route set, signup CTA, professional legal approval, or visual browser validation. |
| C6 — Self-service SaaS and billing | Shared tenancy architecture, lifecycle proposal, plan/entitlement decisions, and Paystack/Flutterwave official documentation comparison. | Official docs researched; no integration tests because no provider adapter exists. | Not implemented. Signup/verification, subscriptions, backend entitlements, sandbox checkout, webhook verification/deduplication/reconciliation, and billing UI remain. |

## Gate assessment

- Gate A — Core integrity: the current PostgreSQL-backed Django suite passes (376 tests); migration drift check reports no changes. No business accounting logic or schema was changed. **Passed for repository tests, not a hosted production database.**
- Gate B — Managed customer readiness: **blocked** by provisioning, invitations, recovery, and PostgreSQL tenant-flow tests.
- Gate C — Operational readiness: **blocked** by unperformed restore drill, missing monitoring/alerts, and lack of external operational setup.
- Gate D — Hosted pilot: **blocked — external actions required**; Compose parsing is not a deployment.
- Gate E — Commercial presentation: **partial**; website and sales/customer drafts exist, but lead capture and approved terms are absent.
- Gate F — Self-service SaaS: **blocked**; architecture and provider research only.
- Gate G — Public launch: **BLOCKED — EXTERNAL ACTIONS REQUIRED**, plus engineering work in C2/C5/C6.

## Validation evidence

- `npm.cmd test`: 236 tests passed across 22 files. A concurrent run during build/typecheck hit one real-mode UI timeout; isolated rerun and full serial rerun both passed.
- `npm.cmd run typecheck`: passed.
- `npm.cmd run build`: passed for mock configuration.
- `VITE_DATA_SOURCE=django VITE_BACKEND_API_URL=/api/v1 npm run build`: passed for Django mode.
- `npm.cmd audit --omit=dev`: 0 vulnerabilities reported for production dependencies.
- PostgreSQL-backed Django suite: 376 passed in 815.77 seconds against a fresh UTF-8 PostgreSQL 17 cluster and explicit pytest temp directory; the disposable cluster and test database were removed afterward. The host PostgreSQL service and any application database were not accessed.
- Django system check and `makemigrations --check --dry-run`: passed against the disposable PostgreSQL configuration; no migration drift.
- Focused JWT suspension, readiness failure, request ID, and OpenAPI checks are included in the full suite and pass.
- Ruff check passed for `backend`; Ruff format check passed for all 233 backend Python files.
- Production Compose config parse: passed with dummy non-secret values; no containers started.
- `bash -n` on backup/verification scripts: passed.
- `git diff --check`: passed.

## Unresolved launch blockers

See [the blocker register](launch-blocker-register.md). Most important: operator onboarding and email identity flows; account recovery and throttling; persisted contact capture; actual restore drill; staging deployment; legal approval; and a tested payment sandbox implementation. The Windows Docker CLI is installed but Docker Desktop's Linux engine pipe is unavailable. The host PostgreSQL service database was intentionally not inspected or touched because its identity/persistence was not established.

## External actions

1. Select and fund hosting, DNS/TLS, private durable storage, and transactional email; configure isolated staging credentials.
2. Select a payment provider account and obtain sandbox/merchant credentials; do not enable live collection yet.
3. Obtain legal review of the privacy notice, terms, DPA, retention, and incident communications before customer contracts.
4. Appoint support/incident contacts and approve support hours, retention, pricing, and service objectives.
5. After C2/C5/C6 engineering and the PostgreSQL/restore tests pass, deploy staging and complete a production go/no-go review.
