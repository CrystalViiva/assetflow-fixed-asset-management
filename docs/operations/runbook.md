# AssetFlow operator runbook (draft)

This is an operational procedure draft for a private/staging deployment. It is not evidence of an exercised production environment.

## Deployment topology

Run the static frontend behind an HTTPS reverse proxy, Django web separately from Celery worker, one Celery Beat instance, PostgreSQL, Redis, and durable private storage. Use managed PostgreSQL with automated point-in-time backups and off-host encrypted backups where possible. Configure object storage as private with versioning and lifecycle controls. Airflow/PySpark is optional and should not be part of the transactional availability path.

## Release

1. Confirm staging and production use separate secrets, database, private storage, email provider credentials, and payment provider credentials.
2. Confirm recent PostgreSQL and private-storage backups exist and the most recent restore drill succeeded.
3. Build immutable application images from the release commit and scan dependencies/images using the chosen CI tools.
4. Deploy the release migration job with the intended database. Review `showmigrations` and `migrate --plan` before applying migrations.
5. Run `collectstatic`, start web/worker, and run the readiness endpoint plus Django-mode smoke checks.
6. Confirm only one Beat scheduler is active. Check worker queue health and failed tasks.
7. Route traffic only after `/api/v1/ready/` succeeds and HTTPS checks pass.
8. Record release commit, migration set, smoke evidence, and operator.

## Rollback

Prefer rolling application images back while keeping additive schema changes in place. Do not automatically reverse a migration that may have processed customer data. For an incompatible schema incident, stop writes, take a verified backup, use the reviewed recovery plan, and record the incident. Never restore over an unidentified database.

## Backup and recovery expectations

Back up PostgreSQL, private evidence, private exports, and configuration required to restore access (secrets are stored in the approved secret manager, not inside the backup bundle). Encrypt backups before leaving the host, restrict access to named operators, alert on missing/failed backups, and define retention with legal/business owners. A database-only backup is incomplete because private file rows refer to file artifacts. Perform restoration into an isolated disposable environment, run integrity/count checks, and record elapsed restore time. No RPO/RTO is promised until a provider and measured restore process exist.

## Incident response

1. Record incident time, reporter, affected service, and severity in the approved incident system.
2. Preserve relevant logs and request IDs; do not copy credentials, tokens, customer evidence, or full personal records into chat or tickets.
3. Contain compromised accounts or service credentials through the authorized provider process. Preserve evidence and audit trail.
4. Assess tenant scope, data confidentiality/integrity/availability, and backup state with the incident lead.
5. Notify management, affected customers, regulators, and providers according to reviewed contractual and legal timelines.
6. Recover from a known-good release or isolated restore. Validate tenant boundaries and accounting records before reopening writes.
7. Record timeline, impact, root cause, actions, and follow-up owners.

The business must designate incident contacts and obtain legal review of notification obligations before launch.

## Tenant suspension and offboarding

Use a reviewed operator-only workflow that records the organization, reason, actor, timestamp, and expiry/review date. Suspension should block authentication and writes while retaining records. Export requested customer data through the supported authenticated export path, verify delivery with the customer, then apply the approved retention schedule. Do not directly delete tenant rows or private objects. Backup copies may retain records until their configured expiry; describe this accurately in the customer notice and DPA.

## Failure triage

- API not ready: check DB connectivity and migration status; readiness response intentionally omits dependency detail.
- Worker backlog: inspect queue depth, worker health, failed task records, and idempotency before replaying jobs.
- Private evidence/export unavailable: check private storage credentials/permissions and artifact integrity; do not make storage public as a workaround.
- Email failure: inspect provider message identifiers and rate limits; safely retry only idempotent notification requests.
- Suspected tenant isolation issue: disable affected access, preserve logs, investigate selectors and background task tenant arguments, and do not inspect unrelated tenant content without authorization.

## Monitoring integration

Poll public `/api/v1/health/` for process liveness and `/api/v1/ready/` for PostgreSQL readiness. Use `python manage.py check_operations` from a restricted monitoring job every minute; nonzero exit means investigation is required. Forward this exit status to the selected alert service. It reports worker heartbeat freshness (three-minute threshold), a private storage write/read/delete probe, pending/exhausted mail deliveries, and failed tasks in the last 24 hours. The same metadata is visible only to operators at `/api/v1/platform/health/`.

The health command also fails for billing reconciliation errors or provider events pending longer than five minutes. Inspect exception types and event IDs, resolve the provider/configuration issue, then use the audited `reconcile_billing_event` command described in the [SaaS operations notes](../saas/implementation.md). Never paste raw webhook bodies, card authorizations or cancellation tokens into incident records.

Run one Beat scheduler. It enqueues identity mail every 30 seconds and worker heartbeat/billing reconciliation every 60 seconds, alongside the six original domain schedules. A missing/stalled worker or broker becomes visible through an aging heartbeat. This is not a direct queue-depth metric or HA guarantee. Failed-task records contain task ID/name and exception type; task arguments and exception messages are excluded. Structured logs retain request correlation IDs and redact credential patterns. Configure log retention and alert recipients at the host; neither is an external service provisioned by this repository.

## Environment and ingress setup

Production must set `ASSETFLOW_ENV=production`, a unique long secret, explicit hosts, an HTTPS frontend URL, a verified sender and transactional email configuration. Development, test, staging and production must use distinct databases, private storage, secrets and mail behavior. Staging accepts captured mail only. Payment collection is forced off in production; the local sandbox cannot be enabled there.

The production frontend binds to loopback on the Docker host, behind the owner's TLS ingress. The ingress must overwrite forwarded protocol/client headers. Set `ASSETFLOW_INGRESS_PROXY_CIDR` to its actual peer network as observed by nginx, and `TRUSTED_PROXY_NETWORKS` to the internal frontend proxy network as observed by Django. Never trust `0.0.0.0/0` or arbitrary forwarded headers. Verify two independent clients receive distinct throttling identities after deployment. Keep the web/database/Redis services private. Nginx's `/api/v1/` location applies an ingress request limit; Django applies atomic identity limits independently.

Backend dependencies are pinned in `backend/requirements.lock` to the tested environment. Regenerate from `requirements.txt`, review, audit and rerun regressions before upgrades. Frontend builds use `npm ci`. Exclude `.codex-*`, environment files and private data from image contexts. Resolve/tag image digests in the actual release registry after container validation; base-image vulnerabilities have not been scanned in this Docker-less environment.

## Reproducible local staging exercise

Create a dedicated loopback PostgreSQL cluster on a nondefault port with an `assetflow` role. Run `python scripts/commercial-smoke.py --port <port>` after installing the locked backend and frontend dependencies and Playwright Chromium. On Windows a known installed Chrome can be selected with `E2E_BROWSER_EXECUTABLE`. The script generates synthetic credentials, migrates its own uniquely named database, starts local Django and Vite, runs four browser journeys, writes evidence, and stops/drops only its own resources. No real SMTP, payment collection or customer database is used. It does not start Redis or validate production Gunicorn/containers.

Adding `--nginx <executable>` builds the Django-mode frontend, syntax-checks a local adaptation of the repository nginx configuration, then runs the same journeys through that real proxy, including security header assertions. This remains a local HTTP test with Django runserver, not a TLS/Gunicorn/Linux deployment.

The production nginx image was updated to upstream stable 1.30.5 after checking the [official release page](https://nginx.org/en/download.html) and [official image source](https://github.com/nginx/docker-nginx). Redis uses a durable AOF volume. Application fonts are vendored with license/provenance records, and nginx sends a same-origin Content Security Policy. Container image scanning and Linux runtime validation remain required on the deployment host.

See [managed onboarding](customer-onboarding.md), [recovery](backup-restore.md), and [release evidence](../commercial/release-decision.md) before accepting a customer.

## Hosting options for evaluation

Two realistic patterns are a managed application platform with managed PostgreSQL/object storage, or a small cloud VM running containers plus separately managed PostgreSQL/object storage. Managed services reduce database backup, patching, failover, and TLS operations; the VM pattern can reduce initial hosting cost but concentrates patching, monitoring, and recovery responsibility on the operator. A single Compose host is not HA and local volumes are not off-site backup. Nigerian-region services may be limited, so compare West Africa latency from intended customer sites with provider support, data location, restore, and export capabilities. Current prices change; obtain quotes from official provider pricing pages at decision time. No pricing estimate or region-specific guarantee is made here.

## Unavoidable external actions before hosting

Choose and pay for a hosting account, configure DNS/TLS, configure a transactional email provider, provision isolated production/staging storage and database credentials in a secret manager, establish incident contacts, and validate restore/monitoring in the selected provider.
