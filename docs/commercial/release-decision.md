# Commercial transformation release decision

**Public launch remains blocked by deployment and operational gates.** The repository has progressed beyond C1: managed onboarding, identity recovery, commercial screens, persisted leads, verified signup and sandbox subscriptions are implemented. No public deployment, production email delivery or merchant sandbox validation is claimed.

## Recovered implementation

The continuation recovered `31b2452`, `3051de3`, `66c61e9` and `6e1e396` after the historical C1 commit. The prior session stopped during documentation updates, after implementing the scheduled financial-posting entitlement guard. Those changes are preserved. See [execution state](EXECUTION-STATE.md) for current work and validation.

| Milestone | Evidence and status | Remaining gate |
|---|---|---|
| C2 - Customer onboarding and identity | Implemented locally: explicit operator capability, idempotent provisioning, activation, scoped invitations/replacement/revocation, transactional mail outbox, password recovery, session revocation, throttling and real Django React screens. PostgreSQL and browser tests exist. | Revalidate continuation and prove delivery with the production mail provider. |
| C3 - Security and reliability | Local security, tenant isolation, dependency health, worker failure records, encrypted database/private-file recovery and financial automation restrictions implemented and tested. | Off-host retention, owner key recovery, deployed alerts and production-volume recovery; durable storage/malware-scanning gate remains partial. |
| C4 - Deployment | Images, production Compose, environment checks, nginx/static hosting, release migrations and local browser smoke tooling implemented. | Linux containers and hosted staging, TLS, ingress identities, actual Redis/Celery runtime and rollback evidence. |
| C5 - Website and sales | Real marketing routes, consented persistent demo/sales requests, operator inbox, customer guides and pilot materials implemented. | Owner-approved pricing/support/legal commitments and hosted browser acceptance. |
| C6 - Self-service SaaS | Verified atomic signup, immutable plan versions, server entitlements, trial/grace/cancel/suspend states, billing UI, local payment simulator and Paystack test transaction transport implemented. | Provider recurring subscription/invoice mapping, stronger integrated journey, merchant sandbox validation. Live collection stays disabled. |

## Recovered validation evidence

- Saved full PostgreSQL JUnit report: **425 passed**, no failures/errors/skips, 762.383 seconds, timestamp 2026-10-09. This is prior-run evidence, not a new test execution.
- Saved encrypted application recovery: two active companies, two managed subscriptions, 67 migration records, four audit events, cross-tenant denial, Decimal sum `1234567890.13`, matching private-file SHA256, wrong-key rejection; 56.70 seconds. The evidence records the checkout's then-HEAD (`1eb4880`) while implementation files were uncommitted. Do not infer that C1 alone supplied these features.
- Local browser runner and four real Django journeys are committed; nginx smoke and build evidence are described in the operations runbook. They do not establish hosted deployment or Docker runtime validation.
- Fresh continuation commands/results are recorded in the execution checkpoint and will supersede historical counts after execution.

## Commercial decision

The application can support a **controlled synthetic/local pilot**. It must not accept a production customer until an owner-controlled staging deployment passes the release smoke, configured mail delivery, backup/restore, alerts, support and contractual review. A managed first customer does not depend on live SaaS payments. Automated paid SaaS additionally requires provider sandbox acceptance and a separately reviewed live-billing release.

Unresolved and locally resolved findings are tracked in the [blocker register](launch-blocker-register.md). Local implementation closure is distinct from operational launch acceptance.
