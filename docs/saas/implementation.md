# SaaS implementation and limits

## Authority and tenancy

The existing shared PostgreSQL schema remains authoritative. `User.organization` represents one organization per account; switching organizations and multiple memberships are not supported. Managed activation and verified signup both create the same Organization/User/Subscription records. Signup first stores a pending Registration and email ticket; there is no active organization or privileged user until verification commits successfully. Operator permission is an explicit server field excluded from tenant serializers.

JWT authentication checks active user, active organization and session version for each request. Tenant-scoped querysets and domain services continue to enforce domain authorization. Subscription expiry blocks unsafe API operations while preserving reads, supported report snapshots/exports, account recovery and billing. Active-user and registered-asset capacity checks hold the organization lock through insertion. Asset counts include disposed records; downgrades never delete records to fit a plan.

## Plans and subscriptions

Plans are immutable versions in PostgreSQL; publish a new version to change price or limits. An operator can unpublish a version without modifying existing subscribers. No tenant API writes plan definitions. The seeded public Team plan is **sandbox sample configuration**, not a commercial offer: NGN 100.00, 14-day trial, 10 active users, 250 registered assets. Managed activation uses a private unlimited plan. Existing organizations without subscription records retain their prior managed access.

States are MANAGED, TRIAL, ACTIVE, PAST_DUE, CANCELED and SUSPENDED. Expiry is evaluated against timestamps on every request, so access does not depend on a scheduler updating a label. The billing screen shows both state and whether writes are allowed. Billing contact and transaction history are persisted. Storage, export volume, optional modules and support tier are not monetized/enforced limits in this release.

Sandbox purchases grant 30-day periods. A same-plan renewal preserves unexpired paid time; a plan change starts a new 30-day period with no proration. A downgrade is rejected if usage exceeds its limits. Failed renewal permits at most seven days after the previously earned period. Cancellation stops trial writes immediately or preserves paid access until its period end. Previously initiated checkouts cannot undo cancellation. A new explicit checkout can resubscribe. Refund/chargeback on the entitlement-granting checkout suspends writes for review, without destroying records.

## Provider boundary

`BILLING_PROVIDER=local_sandbox` is a deterministic local provider with a separate authoritative transaction state, signed event generation, verification, replay deduplication, reconciliation and simulated success/failure/refund/chargeback. It never sends payments. Browser simulation is restricted to the owning tenant's administrator and nonproduction local sandbox mode. Changing a browser redirect cannot grant access.

The Paystack **test transaction** adapter initializes hosted checkout and verifies status, test domain, reference, exact minor amount and currency via the documented API. HMAC-SHA512 verification authenticates raw webhook bodies. An event stores only allowlisted metadata; card details/raw payloads are not stored. Event digests deduplicate delivery; locked transactions and server re-verification handle replay and changed/out-of-order state. Failed verification remains retryable, with an operator reconciliation command. An ambiguous checkout initialization retains its original reference.

Paystack transport contracts were tested with mocked official API responses. No merchant credentials were available and **no request to Paystack's remote sandbox was verified**. Provider-managed recurring subscription creation, provider-specific invoice/refund/dispute event reconciliation and real billing documents remain outside this adapter. The local simulator verifies those application state transitions; it does not prove Paystack's corresponding production behavior. Do not market automated live recurring billing yet.

Official contracts: [Paystack transaction API](https://paystack.com/docs/api/transaction/), [webhook signatures and delivery](https://paystack.com/docs/payments/webhooks/), [subscriptions](https://paystack.com/docs/payments/subscriptions/).

## Environment controls

| Environment | Registration | Billing | Email |
|---|---|---|---|
| Development/test | Enabled by default | Local sandbox | Console/test capture |
| Staging | Configurable | Local sandbox or Paystack `sk_test_` | Capture only |
| Production | Disabled by default; managed onboarding remains available | Must be `disabled`; other values fail startup | Configured transactional provider |

Paystack live keys are rejected. Production payment collection cannot be enabled by a frontend flag. Do not copy development settings into production. The API config endpoint lets the website show available flows without pretending an unconfigured checkout works.

## Executable validation

- `backend/accounts/tests/test_identity.py`: activation/reset replay, expiry, revocation, role and organization injection, shared throttling, concurrency and session revocation.
- `backend/commercial/test_commercial.py`: signup races, backend entitlements, tenant billing isolation, forged/duplicate/out-of-order events, cancellation, failure/grace, refunds, retries and immutable plan terms.
- `e2e/commercial.spec.ts`: real Django/PostgreSQL signup, activation, workspace, invitation, recovery, sandbox billing, managed operator provisioning, persisted lead and mobile marketing journeys.
- `scripts/commercial-smoke.py --port <isolated-port>` owns and cleans its synthetic database; it rejects port 5432. This local smoke does not claim container, remote staging or public deployment validation.

Billing history formats integer minor amounts with integer arithmetic; the browser does not compute financial entitlements. Personal email changes and membership transfers are unavailable through customer profile endpoints until a separate verified workflow is implemented.
