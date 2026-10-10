# Commercial transformation release decision

**The local commercial implementation passes its integrated gates; accepting a production customer remains blocked by deployment and operational acceptance.** Managed onboarding, identity recovery, commercial screens, persisted leads, verified signup, server subscriptions and payment simulation work against real Django/PostgreSQL. No hosted deployment, production email delivery or actual merchant sandbox validation is claimed.

## Implementation status, 2026-10-10

The continuation recovered four completed commits ending at `6e1e396` and preserved the interrupted documentation work. New implementation through `b6f9346` completes test-provider recurring reconciliation, adds the commercial-to-accounting journey and fixes test isolation/deployment policy forwarding. See the [checkpoint](EXECUTION-STATE.md) and [executed validation](validation-2026-10-10.md).

| Milestone | Status and demonstrated behavior | Remaining acceptance gate |
|---|---|---|
| C2 - Customer onboarding and identity | **Complete in local functional scope.** Explicit operator capability, managed provisioning, administrator activation/login, employee invitation/acceptance, password recovery, transactional outbox, throttling and real React screens pass PostgreSQL/API/browser journeys. | Prove production mail delivery and deployed ingress behavior before customer onboarding. |
| C3 - Security and reliability | **Partial.** Tenant isolation, subscription restrictions, worker failure/health records and an actual encrypted PostgreSQL/private-file restore pass. | Off-host retention, owner key recovery, deployed alert delivery, durable storage/scanning policy and production-volume recovery. |
| C4 - Deployment | **Partial; external execution blocked.** Images/configuration, environment checks, migrations and built Django-mode frontend through nginx pass available local checks. | No Docker Linux engine is available. Linux container/Gunicorn/Redis/Celery startup, hosted TLS, ingress, rollback and operational integrations need staging evidence. |
| C5 - Website and sales | **Complete in local functional scope.** Marketing navigation, validated/consented persisted demo and sales requests, operator lead inbox, customer guides and pilot materials are implemented and tested. | Owner-approved pricing, support and legal commitments; hosted acceptance. |
| C6 - Self-service SaaS | **Partial.** Verified atomic signup, immutable plans, server entitlements, trial/grace/cancel/suspend states, billing UI and local simulator pass. Paystack test plan/customer/subscription mapping, verified invoice renewals, cancellation, reversals, replay/concurrency and operator recovery have local contract tests. | Actual merchant sandbox acceptance remains unavailable. Live collection is deliberately disabled; no live SaaS billing release is claimed. |

## Current evidence

- Full backend regression: **439 passed**, zero failures/errors/skips, 1284.53 seconds. Final billing/operations changes were separately validated by **42 passed** and an added **1 passed** operator-retry case. Six cases were added after full-suite collection; these are not described as one final 445-case execution.
- Full frontend regression: **242 passed** across 23 files with thread workers; subsequent commercial regression **7 passed**, including the added provider cancellation/status case. Typecheck/lint and Django-mode production build passed.
- Four real Django/PostgreSQL/nginx/Chrome browser journeys passed with no skips/flakes. A separate integrated journey passed all 20 requested commercial/accounting checkpoints, including retained records after canceled subscription expiry and suspended-session denial.
- Fresh actual encrypted restore: 68 migrations, two active companies, two managed subscriptions, four audit events, cross-tenant denial, Decimal total `1234567890.13`, matching private-file SHA256 and wrong-key rejection; 63.90 seconds. This was executed against owned disposable resources.
- Production Django checks and Compose configuration parsing passed with generated synthetic settings and explicit HSTS domain-policy flags. These checks do not establish container or hosted runtime behavior. Frontend production dependency audit reported zero vulnerabilities; no container-image scan or external penetration test was performed.

## Commercial decision

The application supports a **controlled synthetic/local pilot**. It must not accept a production customer until owner-controlled staging passes the release smoke, mail delivery, backup/restore, alerts, storage, support and contractual gates. A managed first customer does not require live SaaS payments. Automated paid SaaS additionally requires actual provider sandbox acceptance and a separately reviewed live-billing release.

The [blocker register](launch-blocker-register.md) distinguishes local implementation closure from operational launch acceptance. Remaining external work is concrete; completed local workflows should not be rebuilt.