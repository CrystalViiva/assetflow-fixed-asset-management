# F8 — Deterministic assurance and reconciliation

## Contract audited

The public API is `/api/v1/assurance/`. Its run, finding, run-findings, and summary resources are defined by `backend/assurance` views, serializers, selectors, services, permissions, models, tasks, and the M10.5 execution design in `backend/assurance/README.md`. Django owns the run manifest, evaluator decisions, publication, findings, occurrences, and review state.

### Run lifecycle and frozen inputs

Manual creation stores a `PENDING` run with run type, optional completed verification campaign, stale-record threshold, organization and actor. A `PHYSICAL` run requires a completed same-tenant campaign. `execute` commits `RUNNING` and its audit event, then dispatches the Celery task after commit; HTTP 202 means execution was accepted, not completed. `cancel` applies only to `PENDING`. `COMPLETED`, `FAILED`, and `CANCELLED` are terminal; a failed/cancelled execution is repeated by creating a new run. There is no public manual recovery/retry action.

M10.5 captures inputs in PostgreSQL REPEATABLE READ and seals the population before evaluating durable work units. Evaluator and input schema versions are exposed on runs. Once sealed, retry uses the same immutable captured values, even when live asset data changes. API-visible progress is the execution phase, capture/seal timestamps, captured population, and completed/total work units. Final asset and finding counters are only populated at publication. No percentage or candidate counter is fabricated in the browser.

Celery advances one phase or unit per delivery. The database run is authoritative; worker results are not. Unit transactions and run-row serialization make repeated/different-run execution safe according to M10.5 contracts. Transient errors use durable backoff and bounded retries; Beat redispatches eligible current-version RUNNING work. Legacy/incompatible RUNNING records require operator review and are excluded from automatic recovery. The API does not expose a manual recover control.

### Internal execution versus public findings

`AssuranceRunInput`, `AssuranceWorkUnit`, and `AssuranceRunCandidate` are private execution records. They have no public API resource, and F8 defines no endpoint for them. The browser reads only `AssuranceRun`, `AssuranceFinding`, and nested immutable `AssuranceFindingOccurrence` data returned by public serializers/selectors.

The executor evaluates sealed snapshots into internal candidates. Only after every manifest unit succeeds does one atomic transaction publish public finding updates, occurrence snapshots, audit events, counters, and the `COMPLETED` status. If evaluation or publication fails, that transaction rolls back: the run becomes `FAILED` and no public findings or occurrences from that run are published. Internal candidates remain backend history and are never queried or rendered by this client. The run-specific findings endpoint filters public findings by published occurrence for that run; it is enabled in the UI only after authoritative `COMPLETED` state.

### Findings and occurrences

Public findings carry backend type, severity, source, status, expected/observed values, description, asset or physical-observation identity, detection timestamps, occurrence count, resolution data, created/last-detected run, and nested occurrence snapshots. The finding-type and source enums are validated strictly by frontend DTOs. Occurrences preserve one immutable comparison snapshot per detecting run. Repeat detection updates an active finding and adds an occurrence. A finding that reappears after terminal closure is a new finding; absence from a later run does not auto-resolve it. Recurrence is displayed from backend `occurrence_count` and occurrence rows, never inferred from matching browser text.

Review is the domain `review` action (`OPEN` → `UNDER_REVIEW`). `resolve`, `accept`, and `reject` require resolution notes and use their own POST actions. Terminal finding records are immutable. The API has no separate reviewer field/action payload beyond the status transition and audit event; resolver email/time/notes are exposed. Resolving an assurance finding does not update Asset, assignment, location, department, lifecycle, acquisition, or depreciation records.

## Access boundaries

The API derives tenant organization from the signed-in user and applies tenant-scoped querysets. ADMIN and ASSET_MANAGER may create, execute, cancel, review, and close. ACCOUNTANT reads only financial runs/finding types. DEPARTMENT_MANAGER receives department-scoped operational findings but no organization-wide run listing. EMPLOYEE has no assurance access. The screen mirrors those controls for usability; server permissions/object scoping remain authoritative. Cross-tenant UUID substitution returns no scoped object. The run-input/candidate internals cannot be selected by URL.

F7 `VerificationException` and F8 `AssuranceFinding` remain distinct: F7 exceptions are generated/managed by physical observation workflows, while F8 findings are deterministic public records published from a completed assurance run. The UI labels these separately and does not merge their types or status transitions.

## Frontend integration

`assuranceDtos.ts` strictly parses exposed UUIDs, lifecycle statuses, phases, counters, timestamps, nullable relationships, evaluator/input versions, finding enums, resolution metadata, and occurrence snapshots. `assuranceRepository.ts` calls only the public assurance routes. `assuranceQueries.ts` scopes TanStack Query keys by user and session generation, polls active runs every five seconds and selected RUNNING run detail every three seconds, and stops when the returned state is no longer RUNNING. Polling uses query cancellation, authentication, and the existing logout query-cache clear.

The Django Assurance screen provides filtered/paginated run history, manager create/execute/cancel controls, authoritative execution state, public run findings, filtered public findings, occurrence detail, and supported review/resolution actions. It never displays partial candidate results. FAILED runs show a generic authoritative failure state without rendering internal error detail and offer a new-run workflow. The public findings endpoint is the only source of finding cards. Asset Detail has an on-demand, paginated public finding history using the server's `asset` filter and embeds backend occurrence snapshots without per-finding requests.

Run creation compares paginated authoritative pending-run history before and after an ambiguous POST, using newly appearing run UUID plus type, campaign, threshold, actor, and creation time. A unique match is treated as committed; ambiguous/unavailable history blocks another create pending recheck. Execution/cancellation refetch the run after ambiguous results; RUNNING means already dispatched, while a still-PENDING state is explicitly shown before a later user retry. Finding actions refetch the finding after ambiguous responses and only report a transition when Django confirms its status. No non-idempotent request is automatically replayed. Session-generation checks fence every reconciliation. Mutations invalidate only the assurance query family; they do not invalidate asset-master queries.

Mock mode retains its existing `IntegrationPending` behavior and does not show invented assurance data. Django mode has no mock findings or fallback. No report, analytics, or F9 integration was added.

## Smoke and validation

Run `python scripts/f1-smoke.py --f8` in the configured development environment. The runner creates a random `assetflow_f8_*` disposable PostgreSQL database, migrates and seeds it, starts Django on localhost with a smoke-only settings module that executes registered Celery tasks eagerly, exercises the authenticated TypeScript repositories through HTTP, verifies public models/master data/audits in PostgreSQL, then drops only that random database. The eager Celery task is the repository's isolated execution mechanism; it exercises the real API dispatch and evaluator but does not test timing with an external Redis worker. M10.5 backend tests cover transaction interruptions, duplicate task delivery, recovery, transient retries, terminal failures, publication rollback, and legacy-running exclusion.

The fixture's current book value intentionally differs from capitalized cost less accumulated depreciation, producing a deterministic public `BOOK_VALUE_EXCEPTION`. The smoke verifies completed run/version/progress, public occurrence history, review and resolution audit events, unchanged asset master fields and active custody, and logout. No production assurance/concurrency code, migrations, or OpenAPI schema changed for F8.

No F9 reporting work, F7 exception substitution, M11/AI/anomaly logic, private evidence work, or generated analytics artifacts are part of this milestone.
