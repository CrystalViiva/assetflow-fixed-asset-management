# Product functionality matrix

This matrix describes the implemented commercial continuation; see the release decision for validation scope. Django means a real authenticated API backed by PostgreSQL. Mock means fictional browser-local/demo data and is not a customer workspace.

| Surface | Django customer mode | Mock/demo mode | Status and user-facing caveat |
|---|---|---|---|
| Public landing | Public pages, contact/demo forms and login/signup entry | Marketing and labeled illustration; lead submission disabled in mock builds | Django leads persist with consent, throttling and operator status inbox. |
| Login/session | JWT login/refresh, password recovery/change, immediate session version revocation and suspension checks | Demo session behavior | Real identity flows use signed, expiring, single-use email tickets. |
| Dashboard | Live scoped Django/PostgreSQL aggregates | Seeded illustrative data | Real customer data in Django mode. |
| Asset register/details | API-backed search, pagination, detail | Mock repository | Real in Django mode. |
| Acquisition/capitalization | Domain API and Decimal services | Mock workflow | Backend authoritative in Django mode. |
| Depreciation | SLM schedules and period posting APIs | Mock workflow | Existing accounting limitations apply. |
| Assignments/transfers | Scoped API and controlled transitions | Mock workflow | Custody and placement remain separate. |
| Maintenance | Work orders and costs via API | Mock workflow | Operational costs do not alter asset basis. |
| Disposal | Approval and accounting derecognition APIs | Mock workflow | Separate approval and proceeds/carrying value accounting. |
| Physical verification/evidence | Campaigns, records and authenticated private evidence | Mock verification screen | Django evidence is private; no malware scanning. |
| Assurance | Async, durable assurance jobs and findings | Mock assurance | Control checks do not mutate accounting/asset records. |
| Reports/snapshots/exports | Current reports, immutable snapshots, async private exports | Mock reports | Exports are snapshot-derived and authenticated. |
| Audit | Read-only, tenant-scoped API | Mock history | Application audit trail, not cryptographic tamper evidence. |
| User administration | Directory, role/department/status updates and invitations | Mock users/roles screen | Invitations replace initial-password creation in the customer UI; last-admin controls retained. |
| Departments/locations/settings | Reference CRUD, account profile, company name/legal name and password change | Mock settings/reference data | Currency/timezone selected on provisioning; historical accounting currency is not casually editable. |
| Password change/recovery | Forgot/reset/change forms and APIs; generic response and shared throttling | No fake account recovery | Captured-email browser and PostgreSQL replay/session tests pass. |
| Company provisioning | Unscoped operator API, CLI and console; idempotent request and activation | No mock customer provisioning | Pending company activates only after invitation acceptance. |
| Contact/demo request | Persisted enquiries, consent/honeypot/throttling, operator inbox/status and retention review | Clearly unavailable submission | No live sales email sent during tests. |
| Self-service signup/verification | Company registration, resend verification, atomic activation/trial | Signup unavailable in mock mode | Configurable; disabled by default in production. |
| Plans/subscriptions/payments | Server plans, limits, usage/history, cancellation and billing contact | No mock fallback | Local sandbox tested; Paystack test transaction adapter contract-tested only; production charges disabled. |
| Hosting/backup/restore | Hardened Compose, readiness, worker/storage/mail health, encrypted application recovery drill | N/A | Local API/browser/recovery validated. Docker containers and public hosting not validated. |

## Request path

`Browser route → React view → typed repository/query → ApiClient → DRF JWT authentication → tenant-scoped selector/service → PostgreSQL`. Background work is submitted to Celery through Redis; private evidence and exports are accessed through authenticated Django endpoints. Public marketing and login do not load tenant data. In Django mode failed API calls remain errors and do not switch to mock repositories.
