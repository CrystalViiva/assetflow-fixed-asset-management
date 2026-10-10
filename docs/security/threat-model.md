# Security threat model

## Assets and trust boundaries

Assets include customer asset/accounting records, identity credentials and JWTs, private verification evidence and report exports, audit events, email invitations/reset links, and any future subscription/payment metadata. Trust boundaries are the public browser, Django API, PostgreSQL, Redis/Celery workers, private object storage, transactional email, operator tooling, and future payment provider webhooks.

## Threats and controls

| Threat | Existing/required control | Residual risk / verification |
|---|---|---|
| Cross-tenant object access / IDOR | Organization derived from authenticated membership; scoped selectors/querysets; authenticated private downloads. | Run negative API, worker, report, and storage tests for every new endpoint. |
| Tenant admin privilege escalation | Serializer allowlists; explicit unscoped operator capability; no client-supplied org authority. | Provisioning/invitation privilege injection and tenant isolation tests pass; local operator-host access remains privileged. |
| Credential theft/replay | JWT short access lifetime, serialized rotating refresh tokens with blacklist; per-request session version and active-tenant checks. | Reset/change/logout revoke sessions; no application MFA/SSO. Browser storage and XSS remain risks. Restrict operators through an MFA-protected access gateway before hosting. |
| Invitation/reset abuse | Django-signed random tickets, database expiry/revocation/consumption, generic reset/signup responses, atomic throttling and token-free audit. | PostgreSQL concurrency/replay and captured-email browser tests pass; distributed abuse still requires deployed ingress monitoring. |
| Private file exposure | Private storage and authenticated endpoints; size/hash verification. | No malware scanning; provider policy and backup access need validation. |
| Worker tenant confusion/duplicate delivery | Explicit tenant IDs, transactional domain services, task fencing/idempotency where implemented. | New tasks need duplicate, replay, and tenant-context tests. |
| Payment forgery/replay | Signed raw-body events, durable deduplication, locked transitions and independent provider verification; redirects cannot establish payment. | Local sandbox adversarial tests pass. Paystack contracts are mocked; merchant sandbox and provider recurring/refund/dispute behavior are not proven. Production payment collection fails closed. |
| Secret leakage | Environment configuration and ignored local env files; no secrets should enter bundles/logs/commits. | Validate secret scanning and provider key rotation process. |
| Database/storage loss | PostgreSQL/private-file encryption and isolated application restoration passed, including tenant denial and wrong-key rejection. | No off-host backup, production-volume restoration or owner key-recovery evidence. |
| Malicious upload | Restrict type/size and verify file content/integrity; private storage. | Malware scanning/CDR is not implemented. |
| Operator error/insider access | Minimal status metadata, audited provisioning and reasoned suspension, no impersonation/tenant deletion; lead anonymization defaults to dry run. | Operator staffing, restricted infrastructure access, retention/legal holds and emergency approval process require owner configuration. |
| Denial of service/account enumeration | Generic reset/signup responses, shared atomic identity limits, bounded uploads/reports, nginx limits and explicit trusted proxy networks. | No DDoS service or deployed proxy validation; NAT/shared-network limits need pilot observation. |

## Data handling

Never log passwords, access/refresh tokens, reset/invite tokens, payment credentials, or private artifact contents. Audit events should include actor, organization, action, entity identifier, and safe changes, not secrets. Use synthetic data in test/staging. Customer deletion is not a routine admin action; retention, legal hold, and backup expiry require reviewed policy.

## Security claims

Current safe claims are JWT authentication, backend organization/role authorization, private authenticated evidence/export endpoints, and application audit history as implemented. Do not claim a cryptographic ledger, MFA, SSO, malware scanning, external penetration test, certification, or production security validation without evidence.
