# Security threat model

## Assets and trust boundaries

Assets include customer asset/accounting records, identity credentials and JWTs, private verification evidence and report exports, audit events, email invitations/reset links, and any future subscription/payment metadata. Trust boundaries are the public browser, Django API, PostgreSQL, Redis/Celery workers, private object storage, transactional email, operator tooling, and future payment provider webhooks.

## Threats and controls

| Threat | Existing/required control | Residual risk / verification |
|---|---|---|
| Cross-tenant object access / IDOR | Organization derived from authenticated membership; scoped selectors/querysets; authenticated private downloads. | Run negative API, worker, report, and storage tests for every new endpoint. |
| Tenant admin privilege escalation | Serializer allowlists; separate role checks; no client-supplied org authority. | Explicit platform operator boundary and automated negative tests remain required. |
| Credential theft/replay | JWT short access lifetime, rotating refresh tokens with blacklist; HTTPS and secure production cookies. | Access JWT revocation is not immediate; no MFA/SSO; protect browser/device and operator credentials. |
| Invitation/reset abuse | Must use cryptographically strong one-time expiring tokens, generic public responses, throttling, and audit without token material. | Those workflows are absent at the audited baseline. |
| Private file exposure | Private storage and authenticated endpoints; size/hash verification. | No malware scanning; provider policy and backup access need validation. |
| Worker tenant confusion/duplicate delivery | Explicit tenant IDs, transactional domain services, task fencing/idempotency where implemented. | New tasks need duplicate, replay, and tenant-context tests. |
| Payment forgery/replay | Future adapter must authenticate signatures, deduplicate events, reconcile server-side state. | Billing is absent; browser redirects cannot establish payment. |
| Secret leakage | Environment configuration and ignored local env files; no secrets should enter bundles/logs/commits. | Validate secret scanning and provider key rotation process. |
| Database/storage loss | PostgreSQL and private file backups, encryption, access restriction, isolated restore drills. | No validated operational restore evidence yet. |
| Malicious upload | Restrict type/size and verify file content/integrity; private storage. | Malware scanning/CDR is not implemented. |
| Operator error/insider access | Minimal operator metadata, reasoned/audited actions, dry-run destructive workflows. | Operator/support access design and staffing process remain incomplete. |
| Denial of service/account enumeration | Generic auth/reset responses, throttling, bounded uploads/reports, upstream rate limits. | Explicit auth throttling and infrastructure protection need implementation/configuration. |

## Data handling

Never log passwords, access/refresh tokens, reset/invite tokens, payment credentials, or private artifact contents. Audit events should include actor, organization, action, entity identifier, and safe changes, not secrets. Use synthetic data in test/staging. Customer deletion is not a routine admin action; retention, legal hold, and backup expiry require reviewed policy.

## Security claims

Current safe claims are JWT authentication, backend organization/role authorization, private authenticated evidence/export endpoints, and application audit history as implemented. Do not claim a cryptographic ledger, MFA, SSO, malware scanning, external penetration test, certification, or production security validation without evidence.
