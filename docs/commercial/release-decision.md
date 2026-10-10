# Commercial transformation release decision

**The commercial implementation passes local and Linux CI gates, including production containers; accepting a production customer remains blocked by hosted operational acceptance.** Managed onboarding, identity recovery, commercial screens, persisted leads, verified signup, server subscriptions and payment simulation work against real Django/PostgreSQL. No hosted deployment, production email delivery or actual merchant sandbox validation is claimed.

## Implementation status, 2026-10-10

The continuation recovered four completed commits ending at `6e1e396` and preserved the interrupted documentation work. New implementation through `4ff1166` completes test-provider recurring reconciliation, adds the commercial-to-accounting and production-container journeys and fixes test isolation/deployment policy forwarding. See the [checkpoint](EXECUTION-STATE.md) and [executed validation](validation-2026-10-10.md).

| Milestone | Status and demonstrated behavior | Remaining acceptance gate |
|---|---|---|
| C2 - Customer onboarding and identity | **Complete in local functional scope.** Explicit operator capability, managed provisioning, administrator activation/login, employee invitation/acceptance, password recovery, transactional outbox, throttling and real React screens pass PostgreSQL/API/browser journeys. | Prove production mail delivery and deployed ingress behavior before customer onboarding. |
| C3 - Security and reliability | **Partial.** Tenant isolation, subscription restrictions, actual Redis/Celery worker failure/health behavior and an encrypted PostgreSQL/private-file restore pass. | Off-host retention, owner key recovery, deployed alert delivery, durable storage/scanning policy and production-volume recovery. |
| C4 - Deployment | **Partial; hosted acceptance blocked.** Actual production images build and run in Linux CI. Release migrations/static files, Gunicorn/nginx/PostgreSQL/Redis/Celery/Beat, proxy headers, disabled billing and restart persistence pass. | Hosted TLS/ingress, external mail/storage/alerts, rollback and off-host recovery need owner-controlled staging evidence. |
| C5 - Website and sales | **Complete in local functional scope.** Marketing navigation, validated/consented persisted demo and sales requests, operator lead inbox, customer guides and pilot materials are implemented and tested. | Owner-approved pricing, support and legal commitments; hosted acceptance. |
| C6 - Self-service SaaS | **Partial.** Verified atomic signup, immutable plans, server entitlements, trial/grace/cancel/suspend states, billing UI and local simulator pass. Paystack test plan/customer/subscription mapping, verified invoice renewals, cancellation, reversals, replay/concurrency and operator recovery have local contract tests. | Actual merchant sandbox acceptance remains unavailable. Live collection is deliberately disabled; no live SaaS billing release is claimed. |

## Current evidence

- Full backend regression: **445 passed in Linux CI**, 202.09 seconds. This supersedes the local 439-case gate and later 42-case/one-case focused reruns; no test was skipped in the recorded full runs.
- Full frontend regression: **243 passed** across 23 files in Linux CI, 17.32 seconds. Local thread-worker regression passed 242 cases, followed by seven commercial tests including the added provider cancellation/status case. Typecheck/lint and both mock/default and Django-mode production builds passed remotely.
- Four real Django/PostgreSQL/nginx/Chrome browser journeys passed with no skips/flakes. A separate integrated journey passed all 20 requested commercial/accounting checkpoints, including retained records after canceled subscription expiry and suspended-session denial.
- Fresh actual encrypted restore: 68 migrations, two active companies, two managed subscriptions, four audit events, cross-tenant denial, Decimal total `1234567890.13`, matching private-file SHA256 and wrong-key rejection; 63.90 seconds. This was executed against owned disposable resources.
- Production Django checks and Compose configuration parsing passed with generated settings and explicit HSTS domain-policy flags. The subsequent **production-container gate passed in 132.82 seconds**, including real worker scheduling/failure and database/private-file persistence through service restarts. See its [retained JSON evidence](evidence/production-compose-2026-10-10.json). Actual TLS and SMTP remain outside that synthetic ingress exercise. Frontend production dependency audit reported zero vulnerabilities; no container-image scan or external penetration test was performed.

## Commercial decision

The application supports a **controlled synthetic/local pilot**. It must not accept a production customer until owner-controlled staging passes the release smoke, mail delivery, backup/restore, alerts, storage, support and contractual gates. A managed first customer does not require live SaaS payments. Automated paid SaaS additionally requires actual provider sandbox acceptance and a separately reviewed live-billing release.

The [blocker register](launch-blocker-register.md) distinguishes local implementation closure from operational launch acceptance. Remaining external work is concrete; completed local workflows should not be rebuilt.
