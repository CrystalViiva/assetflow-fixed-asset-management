# F10: Audit trail and lifecycle history

## Backend contract

`AuditLog` is an organization-scoped event record with UUID `id`, nullable `user`, `action`, `entity_type`, string `entity_id`, database timestamp, IP address, JSON `changes`, and JSON `metadata`. Domain services call `audit.services.record_event`; the HTTP audit read endpoint does not create events. Asset, acquisition/capitalization, depreciation, assignment/transfer, maintenance, disposal, verification, assurance, and reporting services emit events where their service implementations call this helper. The event actor is the linked user on that event, not the viewer. The read contract returns the actor email, or null when the actor link has been removed; it does not assert a historical role snapshot.

The model rejects ordinary ORM instance saves, queryset updates, instance deletes, and queryset deletes after insertion. These are application controls, not a cryptographic or tamper-evident ledger guarantee. The API is GET-only at `/api/v1/audit/events/`; POST, PUT, PATCH, and DELETE are not routed. Its explicit response excludes IP addresses and organization internals. JSON metadata/change keys that identify passwords, tokens, authorization, API keys, secrets, credentials, or cookies are redacted recursively on the server, with a second defensive redaction in the frontend.

The endpoint is scoped by the authenticated user's server-derived organization. It permits ADMIN, ASSET_MANAGER, and superuser roles; other roles receive a denial. Supported server-side filters are action, entity type, exact entity ID, actor email, search, inclusive date bounds, timestamp ordering, and standard page/page-size pagination (25 default, 100 maximum). Stable ordering adds the event UUID as a tie-breaker. It does not permit arbitrary ordering or unbounded filter strings.

## Audit versus lifecycle history

The Audit Log is the raw event/control record. F9's `lifecycle_history` is a reporting query over selected AuditLog fields (`id`, `timestamp`, `action`, `entity_type`, `entity_id`, `user_email`); it is a report row projection, not a separate lifecycle event store or a reconstruction of asset state. Assignment, transfer, maintenance, depreciation, verification, finding occurrence, and disposal histories remain their own domain records and carry their own semantics. The Django Asset Detail Audit section requests exact `entity_type=ASSET` and `entity_id=<asset UUID>` events only. Other existing domain-specific Asset Detail sections show their respective authoritative histories; F10 does not imply every linked domain event has an asset foreign key.

## Frontend behavior

The Django Audit Log uses strict `AuditEvent` and paginated DTO parsing, the centralized authenticated API client, TanStack Query keys scoped by user and session generation, and server pagination/filtering. Unknown action strings remain visible as raw identifiers. Actor and event time come from the backend. Change and metadata JSON is rendered as text with native disclosure controls; HTML is never interpreted. No audit mutations are present in the Django repository or UI. Django-mode pages never use the mock audit repository. Mock mode remains explicitly labeled as static local sample activity; mock domain operations do not generate client-side audit records, and the UI makes no cryptographic-ledger claim.

Asset Detail fetches one paginated, exact asset-entity audit query only when its Audit section is selected, avoiding fan-out. It presents those events as audit records and explicitly keeps domain-specific history separate. The global F9 Reports Center remains the place to query the `lifecycle_history` report; F10 does not duplicate the reporting workflow.

## Security and limitations

Tenant ownership is selected by Django from the authenticated user, never from a client-supplied organization ID. Asset ID filtering is an exact filter inside that organization. Department managers and employees are not granted the broad audit explorer because the current AuditLog contract does not preserve sufficient department scope for every event and its before/after metadata. Accountant access is likewise not granted by this endpoint. The backend remains the authorization boundary.

The model's actor FK can be nulled on user deletion and reflects the linked account's current email if it changes; no immutable actor email/role snapshot exists in this contract. Asset Detail's audit section includes only events whose audited entity is the asset itself; events about linked acquisition, assignment, transfer, work order, or other objects are shown in their existing domain sections where available. Sensitive-key redaction covers obvious credential-bearing names; it cannot recognize secrets stored under innocuous key names, so services must not place secrets in audit JSON.

## Validation and smoke

The disposable F10 smoke uses the existing PostgreSQL smoke runner (`python scripts/f1-smoke.py --f10`). It creates a tenant and a second tenant, performs real asset create/update and acquisition capitalization API operations, reads the generated audit events through the TypeScript repository, checks actor/time and asset filtering, confirms all audit write HTTP methods are unavailable, switches tenants and confirms foreign events are absent, then verifies disposable database contents and drops only its generated database. The persistent application database is not used.

No lifecycle-history schema, F11 role administration, F13 dashboard work, or M11/AI work is added. No binary/private evidence or generated analytics artifacts are created.
