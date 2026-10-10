# Commercial architecture and decision record

## Existing authority

Keep the current React/TypeScript browser and Django REST/PostgreSQL domain architecture. `Organization` is the existing tenant key; `User.organization` is the membership boundary. Domain selectors/services, not frontend-supplied organization identifiers, own authorization and financial transitions. PostgreSQL remains authoritative for asset/accounting/audit/report state. Celery/Redis supports retryable async work. Private evidence and exports stay out of public static/media routes. Airflow/PySpark remains optional and separately operated.

## Managed onboarding and SaaS convergence

Managed onboarding and self-service registration must converge on the same organization and membership model. Managed provisioning creates an inactive organization and a single-use expiring activation ticket; the administrator account is created only when activation is accepted. Self-service stores a pending registration, then creates organization, administrator and trial subscription atomically after email verification. Managed provisioning is restricted to an explicit platform operator or CLI command; tenant admins may invite users only into their own organization. Public signup never accepts an operator role or organization identifier as authority. Subscription and entitlement state belongs in server-side records/configuration and is checked by Django at the service/API boundary.

## Operator and tenant boundaries

Treat global operator authority as separate from `UserRole.ADMIN`. Django `is_superuser` remains a framework-level emergency/site-admin privilege, not a tenant-admin feature. Operator workflows should expose status and minimal support metadata; exceptional cross-tenant content access requires a separate, time-limited, reasoned, audited support-access design. Every background task carries an explicit organization and re-resolves scoped records at execution time. Tenant suspension must deny new requests and invalidate/reject existing JWT-authenticated requests through active membership checks; suspension must never delete customer records.

## SaaS lifecycle target

Proposed lifecycle: `PENDING_VERIFICATION → TRIAL/ACTIVE → PAST_DUE/GRACE → RESTRICTED/SUSPENDED → CANCELED/RETENTION → deletion eligible`. Plan definitions are versioned server-side. Entitlements may eventually cover active users, assets, storage, exports, modules, and support, but commercial decisions and caps are not yet selected. Expiration restricts writes or workspace access without deleting business records. Provider webhooks are signature-verified, deduplicated, replay-safe, and tolerant of out-of-order delivery. Redirects from a checkout page never prove payment.

## Initial hosting approach

Use a managed PostgreSQL service with point-in-time/automated backups, one small container service for Django web and Celery worker processes, managed Redis when operationally justified, and private object storage with versioning/lifecycle rules. Serve the Vite static frontend behind a CDN/TLS edge or same-origin reverse proxy. Run one Celery Beat instance. Keep Airflow/Spark outside the transactional service. Exact providers and current costs must be rechecked when choosing an account; no pricing is asserted here. A single-host Docker Compose arrangement is useful for private evaluation, but its local volumes are not a multi-zone or off-host recovery strategy.

## Decisions still requiring evidence

- Select hosting region/provider after comparing current managed PostgreSQL, object storage, backup, TLS, and support offerings.
- Select transactional email provider and verify deliverability, data processing, and Nigeria/international coverage.
- Select payment provider after validating NGN and recurring billing capabilities against current official provider docs and business eligibility.
- Define trial, plan caps, pricing, retention, support hours, incident notification, and service objectives as business decisions.
- Obtain qualified legal review for Nigeria Data Protection Act obligations, international transfer terms, privacy notice, DPA, service terms, and cancellation/refund policy.

No external cloud account, DNS zone, mail provider credentials, or live payment credentials are configured in this repository. No public deployment or live billing is claimed.

## Implemented continuation

The original lifecycle above records the C1 design. Current state transitions, shared subscription model, server entitlements, plan rules and provider limitations are documented in [the implemented SaaS architecture](../saas/implementation.md). Operator and customer procedures are in [managed onboarding](../operations/customer-onboarding.md).
