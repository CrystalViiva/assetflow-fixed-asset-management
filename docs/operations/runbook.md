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

## Hosting options for evaluation

Two realistic patterns are a managed application platform with managed PostgreSQL/object storage, or a small cloud VM running containers plus separately managed PostgreSQL/object storage. Managed services reduce database backup, patching, failover, and TLS operations; the VM pattern can reduce initial hosting cost but concentrates patching, monitoring, and recovery responsibility on the operator. A single Compose host is not HA and local volumes are not off-site backup. Nigerian-region services may be limited, so compare West Africa latency from intended customer sites with provider support, data location, restore, and export capabilities. Current prices change; obtain quotes from official provider pricing pages at decision time. No pricing estimate or region-specific guarantee is made here.

## Unavoidable external actions before hosting

Choose and pay for a hosting account, configure DNS/TLS, configure a transactional email provider, provision isolated production/staging storage and database credentials in a secret manager, establish incident contacts, and validate restore/monitoring in the selected provider.
