# Product functionality matrix

This matrix describes the reviewed repository baseline. Django means a real authenticated API backed by PostgreSQL. Mock means fictional browser-local/demo data and is not a customer workspace.

| Surface | Django customer mode | Mock/demo mode | Status and user-facing caveat |
|---|---|---|---|
| Public landing | Public product description and login entry | Same page | Functional presentation; no lead capture/signup at audit start. Preview is labeled illustrative. |
| Login/session | JWT login, `/me`, in-memory access token, session refresh, sign out | Demo authentication/session behavior | Functional, but recovery/verification/invite flows absent. |
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
| User administration | Tenant-admin API for role/department/status and directory | Mock users/roles screen | Real but initial-password creation is unsuitable for managed onboarding. |
| Departments/locations/settings | Real reference APIs where exposed | Mock settings/reference data | Organization profile administration is incomplete. |
| Password change/recovery | No recovery routes at audit start | Demo behavior only | Not commercially complete. |
| Company provisioning | No product flow; installation bootstrap is operator-managed | Demo data | Requires secure managed provisioning. |
| Contact/demo request | No persisted server workflow at audit start | Static presentation | Not a functioning lead capture workflow. |
| Self-service signup/verification | Absent | Absent | No public tenant creation. |
| Plans/subscriptions/payments | Absent | Absent | No billing capability; do not imply checkout. |
| Hosting/backup/restore | Compose deployment files only | N/A | No external staging/production evidence. |

## Request path

`Browser route → React view → typed repository/query → ApiClient → DRF JWT authentication → tenant-scoped selector/service → PostgreSQL`. Background work is submitted to Celery through Redis; private evidence and exports are accessed through authenticated Django endpoints. Public marketing and login do not load tenant data. In Django mode failed API calls remain errors and do not switch to mock repositories.
