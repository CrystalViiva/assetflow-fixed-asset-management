# F7 — Physical verification

## Contract audited

The source of truth is `backend/verification` models, selectors, services, serializers, views, permissions, URLs and tests. The API is rooted at `/api/v1/verification/`: campaigns, records (physical observations), exceptions and evidence. Standard pagination is 25 rows, configurable up to 100. Django owns filtering, ordering, tenant/department scoping, counts, comparison outcomes, exceptions and audit events.

### Campaigns

`VerificationCampaign` stores organization, name, description, status, scope type, optional department or location, start/due dates, opened/completed times, actors and audit timestamps. Status values are DRAFT, OPEN, IN_PROGRESS, COMPLETED and CANCELLED. Scope is ORGANIZATION, DEPARTMENT or LOCATION, with exactly the corresponding scope reference. Due date cannot precede start date. Campaigns are retained as audit history.

Creation is permitted to ADMIN and ASSET_MANAGER, and starts DRAFT. Only DRAFT campaigns can be edited. `start` changes DRAFT to OPEN. The first accepted observation changes OPEN to IN_PROGRESS. `complete` accepts OPEN or IN_PROGRESS. `cancel` accepts DRAFT, OPEN or IN_PROGRESS. Terminal transitions are rejected on replay. Campaign writes and audit events are transactional and campaign transitions lock the campaign row.

Expected assets are capitalized assets with ACTIVE, IN_MAINTENANCE, TRANSFERRED or IMPAIRED status, filtered by the declared scope. Django calculates expected, verified, unverified, exception and resolved counts and percentage in the campaign selector. Verified coverage counts distinct expected registered assets; unregistered observations do not increase it. These are shown directly from Django.

### Observations and reconciliation

`PhysicalVerification` stores campaign, optional asset link, server timestamp and observer, observed location/department/custodian, condition, observed tag, description and notes. The API derives organization and observer from the authenticated user; result and verification timestamp are read-only. Physical facts cannot be edited or deleted after creation.

Registered observations use an organization-scoped Asset UUID and must be within the campaign's department/location scope. A campaign can contain only one registered observation per asset. An unregistered observation has no asset link and result `UNREGISTERED_ASSET`; for scoped campaigns, Django fills an omitted matching observed department/location from the campaign scope and validates the observed location/department. Unregistered records have no unique-per-campaign constraint. Same-tag observations are instead detected and can update reconciliation summaries and add duplicate-tag exceptions to the affected observations.

Django compares the observed tag, location, department, active assignment/custodian, and condition against the linked asset. It also flags invalid lifecycle status (DRAFT, PENDING_CAPITALIZATION or DISPOSED) and damaged/critical condition. Result values are VERIFIED, LOCATION_MISMATCH, CUSTODY_MISMATCH, CONDITION_MISMATCH, ASSET_NOT_FOUND, TAG_MISSING, DAMAGED, UNREGISTERED_ASSET, DUPLICATE_TAG and OTHER_EXCEPTION. Result is a backend-derived summary with a defined priority; the exception rows preserve the individual detected dimensions. There is no separate observed-lifecycle field and no independent browser-side reconciliation. The backend's `reconcile-missing` campaign action exists, but F7 does not invoke it automatically.

An observation is evidence, never an asset mutation. The frontend sends only verification fields and never patches an asset, assignment, acquisition, depreciation or lifecycle endpoint. Mismatch state and coverage are read from Django.

### Exceptions and evidence

`VerificationException` is created transactionally from detected reconciliation conditions and can also be manually created by a supported API. Types include location/department/custody/condition mismatch, tag missing/mismatch, asset not found, damaged/unregistered asset, duplicate tag, lifecycle mismatch and other. Severity is LOW/MEDIUM/HIGH/CRITICAL. Status is OPEN, UNDER_REVIEW, RESOLVED, ACCEPTED or REJECTED. Exceptions retain assignment, review and resolution actor/time/notes/reference fields. F7 displays authoritative exception rows and integrates the backend assignment, `start-review`, `resolve`, `accept` and `reject` actions with status/exception refetch after ambiguous responses. Resolution never changes asset master data.

Evidence metadata is linked to an observation and optionally one of its exceptions. It exposes type, file name/content type, external reference, captured time/actor, description and integrity metadata. F7 reads metadata and can add a NOTE record, which Django marks `METADATA_ONLY`. It does not send storage keys or files. Private durable binary upload/retrieval is a separate backend workflow and remains outside this F7 UI scope.

## Tenant boundaries and role behavior

The API derives organization from the authenticated user. Campaign and reference serializers/querysets are organization-scoped; asset, location, department and custodian input references are likewise scoped. Campaign and record selectors restrict department managers to their department; campaign mutation is ADMIN/ASSET_MANAGER only, while a department manager can create observations only in a matching department campaign. Read access is ADMIN, ASSET_MANAGER, ACCOUNTANT and DEPARTMENT_MANAGER. Exception mutation is restricted to managers. The UI hides controls by role, while Django remains authoritative. Employee roles have no verification UI access. UUID path substitution is answered through scoped querysets and object permissions.

## Frontend integration

`verificationDtos.ts` strictly validates UUIDs, nullable references, dates/timestamps, all contract enums, progress counts and evidence integrity metadata. `verificationRepository.ts` calls the real API. `verificationQueries.ts` scopes TanStack keys by authenticated user and session generation and exposes paginated campaign, observation, exception and selected-observation evidence queries. The Django operations screen is linked from the sidebar; mock mode displays the existing integration-pending shell and does not show fabricated verification rows.

Create, transition, observation, exception and evidence writes have no automatic retry. Campaign and exception transitions re-fetch the authoritative record after an ambiguous failure. Campaign and observation creation snapshots history and compares newly appearing rows against the submitted identity; multiple or inconclusive matches leave the UI in an explicit uncertain state and block another write pending a recheck. Registered observation identity uses campaign plus asset UUID. Unregistered matching uses all submitted observable fields, and intentionally becomes uncertain if it cannot uniquely identify the committed record. Evidence-note creation similarly rechecks new metadata by its linked observation, note text and external reference. Session-generation checks fence post-write reconciliation and targeted verification-family invalidation. Observation changes do not invalidate asset-master queries. Session logout clears the query cache through the existing F1 session implementation.

The screen supports server campaign filtering/pagination, authoritative progress, start/complete/cancel, registered and unregistered observations, server reconciliation/exception display, exception status filtering and workflow actions, and NOTE evidence metadata. It can load a single selected registered asset and its active assignment on demand for a read-only side-by-side comparison; the list does not issue per-row asset requests. Managers can choose an observed custodian from the tenant-scoped custodian reference endpoint. Department managers do not receive that list because the backend reference endpoint denies their role. Reference lists and the asset list are loaded in bounded collection queries. Asset Detail has an on-demand Verification tab backed by one paginated asset-filtered records request; it does not fan out one request per observation.

## Smoke and limitations

Run `python scripts/f1-smoke.py --f7` from a configured development environment with its disposable PostgreSQL prerequisites. It creates a random `assetflow_f7_*` database, runs Django migrations, seeds only isolated fixtures, starts a local Django server, executes the TypeScript HTTP smoke, verifies database/audit state, then drops only that random database. It never targets the configured application database. The TypeScript flow checks matching and mismatching registered observations, an unregistered item, exception/evidence history, campaign completion, asset and assignment invariance, and unregistered asset count.

No backend changes, migrations, F8 AssuranceRun/Finding work, M11/AI work, or new binary evidence storage implementation are part of F7. The frontend does not expose manual exception creation. Department managers cannot select an observed custodian because the existing custodian-reference API is manager-only; Django continues to enforce tenancy and department scope on submitted records.
