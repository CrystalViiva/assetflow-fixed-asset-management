# C1 — Commercial readiness audit

## Scope and evidence

Reviewed the actual `main` checkout at `488c1961c0e09e1aa1b111d0baf3509ea42224a5`, matching `origin/main`, with a clean worktree at inspection. Source review covered Django settings/URLs and account/organization APIs, model and migration boundaries, Celery, private file storage, report/export paths, the React route/auth/repository boundary, Dockerfiles and Compose files, existing release evidence, tests, and current documentation. The existing F16 release evidence is historical evidence for that revision, not a claim that this commercial transformation has passed its gates.

## Request and data flow

The browser loads the Vite-built React application. Public landing/login routes are separated from authenticated workspace routes. In Django mode, typed repositories call the DRF API through `ApiClient`; the client holds the access token in memory, stores the rotating refresh token in session storage, refreshes after 401, and fences responses by session generation. It does not fall back to mock data on API failure. Django REST Framework authenticates JWTs, derives organization scope from the authenticated user, then calls app selectors/services. PostgreSQL is the source of truth for users, organizations, assets, lifecycle events, accounting, reports, and audit records. Celery uses Redis for asynchronous assurance/export/analytics work. Verification evidence and report exports use configured private Django storage and authenticated content endpoints. The separate Airflow/PySpark workload consumes snapshot-derived contracts; it is not required for serving transactional requests.

## Product findings

The repository already has a real fixed-asset lifecycle and accounting implementation, including acquisition, capitalization, SLM schedules/postings, transfer, maintenance, disposal, verification, assurance, audit, dashboard, snapshots, and private exports. The public landing page accurately labels its preview as illustrative and explains the SLM/accounting limitations. The application has login and tenant-admin user CRUD, but tenant admins provision users by assigning an initial password; there is no invite/activation, password recovery, self-registration, organization provisioning command/API, contact/demo capture, subscription, or billing implementation. The in-app `UsersRolesView` is the mock-mode administration surface; Django mode has a separate backend administration screen. The marketing-to-app entry point is login/dashboard; routes and their exact backed capabilities are in [the functionality matrix](product-functionality-matrix.md).

## Security and operational findings

Tenant scope is consistently server-derived on reviewed user-admin and domain surfaces; organization administrators are distinct from Django superusers. The custom user model has no platform-operator role or ownership lifecycle. JWT access expires after 15 minutes and refresh after one day, with rotation/blacklisting. The configured authentication has no explicit throttling. Password recovery is absent. Existing tenant-admin creation accepts passwords directly, which is unsuitable for commercial onboarding. Production settings require a secret when `DEBUG=false`, but have an explicitly insecure local key for debug; Compose production requires host/secret values. The production Compose topology uses a local PostgreSQL volume and private file volume, but has no backup/restore automation, transactional email settings, monitoring integration, or live cloud deployment evidence. Health currently reports process liveness without checking dependencies. Private exports/evidence have authenticated endpoints and integrity checks; malware scanning is not implemented. Existing release evidence documents accounting boundaries and tests; this audit does not claim independent security certification or legal compliance.

## Accounting boundaries

Preserve the existing Decimal-backed accounting services and the documented SLM conventions. Existing supported behavior includes componentized acquisition costs, capitalization, period-controlled sequential postings, residual-value floor/final-period rounding, disposal gain/loss, immutable report snapshots, and verification/assurance non-mutation. The product does not implement full IAS 16/IFRS compliance, component depreciation, revaluation, IAS 36 impairment ledger, estimate revisions, decommissioning obligations, or multi-currency accounting. These limitations are explicit in README and accounting documentation.

## Release classification at audit start

- Managed onboarding: blocked by the absence of operator provisioning, invitation, and reset flows.
- Customer account administration: partial; tenant-scoped user CRUD exists, but onboarding/security lifecycle is incomplete.
- Hosted pilot: not demonstrated; Compose exists, but there is no verified external deployment, durable managed storage configuration, backup restore evidence, operational monitoring, or email provider.
- Self-service SaaS and billing: absent.
- Public commercial presentation: partial; a credible landing page exists, but no lead capture, complete sales/customer materials, or approved legal documents.
- Accounting core: established implementation with historical test evidence; current validation is required before release.

See [launch blocker register](launch-blocker-register.md), [product functionality matrix](product-functionality-matrix.md), and [commercial architecture](commercial-architecture.md).
