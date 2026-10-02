# API foundation

AssetFlow API routes are versioned under `/api/v1/`. OpenAPI is available at `/api/v1/schema/`, with Swagger UI at `/api/v1/docs/` and ReDoc at `/api/v1/redoc/`.

## Authentication

Private API views require a SimpleJWT bearer access token. Obtain an access/refresh pair with `POST /api/v1/auth/token/` using `email` and `password`. Refresh the access token with `POST /api/v1/auth/token/refresh/` and the current refresh token. Access tokens are short lived; refresh tokens rotate and the consumed refresh token is blacklisted.

`GET /api/v1/auth/me/` is a protected foundation endpoint and returns the authenticated user's id, email, and role. `GET /api/v1/health/` is a public process health check and does not disclose database or secret configuration.

## Error response

DRF errors use this envelope while preserving normal HTTP status codes:

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The request contains invalid fields.",
    "details": {"field": ["A useful field-level explanation."]}
  }
}
```

Known error codes include `VALIDATION_ERROR`, `AUTHENTICATION_ERROR`, `PERMISSION_DENIED`, `NOT_FOUND`, and `API_ERROR`. Unexpected server errors are handled by Django's production error handling and are not converted into responses containing stack traces.

## Pagination

List endpoints use DRF page-number pagination with a default page size of 25 and response keys `count`, `next`, `previous`, and `results`. Clients may set `page` and `page_size` (up to 100); larger page sizes are capped.

## Asset master data

- `GET/POST /api/v1/assets/` list and create assets.
- `GET/PATCH/PUT /api/v1/assets/{id}/` retrieve or update an asset. Physical deletion is not exposed.
- `GET /api/v1/assets/by-tag/{asset_tag}/` retrieve an asset by its organization-scoped tag.
- `GET/POST /api/v1/assets/categories/` list or create categories.
- `GET/PATCH/PUT /api/v1/assets/categories/{id}/` retrieve or update a category. Physical deletion is not exposed.
- `GET /api/v1/departments/` and `GET /api/v1/locations/` return organization-scoped, paginated reference choices (`id`, `organization_id`, `name`, `code`, `is_active`). These lookup routes are read-only and require an authenticated organization member.

Asset lists accept `status`, `category` (UUID) or the frontend-compatible `category__name`, `department` or `department__name`, `location` or `location__name`, `manufacturer`, `acquisition_date_after`, `acquisition_date_before`, `search`, and `ordering`. Search checks tag, name, serial/model number, manufacturer, and description. Ordering is limited to explicitly supported fields.

Asset payloads use domain names such as `asset_tag`, `purchase_cost`, and `current_book_value`. Related category, department, and location IDs are accepted as `category_id`, `department_id`, and `location_id`; responses include their names and codes. Organization ID and lifecycle/accounting snapshots are read-only. `current_book_value` and `accumulated_depreciation` are reserved for later posting services.

For ACTIVE assets, a PATCH/PUT that changes department or location returns a validation error directing the caller to the transfer workflow. Draft placement may be edited as master data. Approved transfer completion remains the API workflow for active placement changes.

ADMIN and ASSET_MANAGER can write asset/category master data. ACCOUNTANT is read-only. DEPARTMENT_MANAGER reads their configured department's assets; EMPLOYEE reads active assets in their organization. All querysets are tenant-scoped.

## Acquisitions and capitalization

- `GET/POST /api/v1/assets/acquisitions/` lists organization-scoped acquisitions or records an acquisition against a draft asset.
- `GET/PATCH/PUT /api/v1/assets/acquisitions/{id}/` retrieves or updates a draft acquisition.
- `POST /api/v1/assets/acquisitions/{id}/capitalize/` performs the controlled capitalization transition.

Acquisition input accepts `asset_id`, `vendor_name`, `invoice_number`, `reference`, `acquisition_date`, optional `capitalization_date` and `currency`, plus `purchase_price`, `freight_cost`, `installation_cost`, `civil_works_cost`, and `other_capitalizable_cost`. `total_cost`, acquisition status, organization, and actor fields are server-controlled; any client-supplied read-only value is ignored. The cost total is calculated from the five components. Currency defaults to the organization's base currency; until foreign-exchange support is implemented, an acquisition must use that base currency.

ADMIN and ASSET_MANAGER can create, update, and capitalize acquisitions. ACCOUNTANT can read organization acquisitions. DEPARTMENT_MANAGER can read acquisitions for assets in their department. EMPLOYEE has no acquisition API access. Acquisitions are tenant-scoped and cannot be deleted through the API.

## Depreciation and accounting periods

- `GET/POST /api/v1/depreciation/schedules/` lists schedules or generates the one schedule for an asset. Creation accepts `asset_id`; all assumptions are read from its capitalized asset record.
- `GET /api/v1/depreciation/schedules/{id}/` retrieves an organization-scoped schedule.
- `GET /api/v1/depreciation/entries/` lists posted entries. `POST /api/v1/depreciation/entries/post/` posts one using `{ "asset_id": "…", "period_id": "…" }`.
- `GET/POST /api/v1/depreciation/periods/` lists periods or explicitly opens a month with `{ "year": 2025, "month": 2 }`.
- `POST /api/v1/depreciation/periods/{id}/close/` closes an open period and records the actor and timestamp.

ADMIN, ASSET_MANAGER, and ACCOUNTANT may generate schedules, post depreciation, and manage periods. DEPARTMENT_MANAGER receives read-only depreciation access for assets in their department; EMPLOYEE has no depreciation access. Data is organization-scoped. Schedule lists support asset, tag, method, status, and start-date filters; entry lists support asset, tag/search, method, period ID or `YYYY-MM`, year/month, and period date bounds. Period lists support year, month, and status. The list endpoints use shared page-number pagination and allow-list ordering.

## Assignments and transfers

- `GET/POST /api/v1/assets/assignments/` lists custody history or opens an assignment. Creation accepts `asset_id`, optional nullable `assigned_to_id`, `department_id`, `location_id`, optional `assigned_at`, and `notes`.
- `GET /api/v1/assets/assignments/{id}/` retrieves an organization-scoped assignment. `POST /api/v1/assets/assignments/{id}/return/` closes the active assignment and records the actor/time.
- `GET/POST /api/v1/assets/transfers/` lists transfer history or requests movement using `asset_id`, destination `to_department_id`/`to_location_id`, `reason`, and optional `notes`. Source department/location are server-captured from the asset.
- `GET /api/v1/assets/transfers/{id}/` retrieves a transfer. POST actions `/approve/`, `/reject/`, `/cancel/`, and `/complete/` advance valid workflow transitions. State, actor, and timestamps are server-controlled.

For an ACTIVE asset, assignment creation may record its current department/location but cannot change either placement value; request and complete a transfer for movement. Assignment remains the custody workflow and does not create a transfer implicitly.

List endpoints are paginated and organization-scoped. Assignment filters include asset, assigned user, department, location, and `active=true|false`; transfer filters include asset, status, source/destination department/location. Both support search and allow-listed ordering. ADMIN and ASSET_MANAGER may mutate workflows. ACCOUNTANT reads organization records; DEPARTMENT_MANAGER reads records involving their department; EMPLOYEE reads assignments to them and transfers for assets currently assigned to them. Historical records are not physically deleted. Assignment denotes custody; transfer changes the asset department/location snapshot and does not implicitly alter custody.

## Maintenance and work orders

- `GET/POST /api/v1/assets/maintenance-plans/` lists or creates plans. `GET/PUT/PATCH /api/v1/assets/maintenance-plans/{id}/` retrieves or updates a plan; plans are deactivated rather than deleted.
- `GET/POST /api/v1/assets/work-orders/` lists or creates operational orders. Detail actions are `POST /assign/` with `assigned_to_id`, `POST /start/` with no body, `POST /complete/` with `resolution` and optional completion notes/downtime/performer/date, and `POST /cancel/` with an optional reason.
- `GET/POST /api/v1/assets/maintenance-costs/` lists costs or adds a cost to a nonterminal work order. Inputs include work order, type, description, quantity, unit cost, and optional vendor reference/date; `total_cost` is calculated server-side.
- `GET /api/v1/assets/maintenance-records/` lists permanent records created as part of work-order completion; detail retrieval is also available.

Lists are paginated, organization-scoped, searchable, and have allow-listed ordering. Plans filter by asset/type/active/due date; work orders by asset/type/priority/status/assignee/due date/opened date; costs by work order/type; records by asset/type/maintenance date. ADMIN and ASSET_MANAGER may create/update plans, operate work orders, and add costs. Other roles are read-only and limited by department or current assignment scope. Completed work orders, costs, and records are not edited or deleted through the API. Plans store scheduling intent only; automatic scheduling is not implemented.

## Disposals and derecognition

- `GET/POST /api/v1/assets/disposals/` lists organization-scoped disposal workflows or creates a DRAFT request.
- `GET/PATCH /api/v1/assets/disposals/{id}/` retrieves a disposal or updates editable DRAFT fields. Physical deletion is not exposed.
- `POST /api/v1/assets/disposals/{id}/submit/` submits a draft for approval; `/approve/`, `/reject/`, and `/cancel/` advance valid workflow transitions; `/complete/` performs transactional derecognition.

Creation accepts `asset_id`, `disposal_date`, `disposal_method`, `reason`, `proceeds`, and optional `currency`. Proceeds must be nonnegative; currency defaults to the organization's base currency and FX conversion is not supported. Status, actor/timestamps, carrying amount, capitalized cost snapshot, accumulated depreciation snapshot, and gain/loss are server-controlled. Completion returns the completed disposal with its accounting snapshots. Carrying amount is the locked asset capitalized cost less posted accumulated depreciation; gain/(loss) is proceeds less carrying amount.

Lists support filters for asset, status, method, requester, approver, department, location, disposal-date bounds, and gain/loss bounds, along with search and allow-listed ordering. ADMIN and ASSET_MANAGER may manage the workflow. ACCOUNTANT has read access; DEPARTMENT_MANAGER reads records for their configured department; EMPLOYEE has no disposal access. Requesters cannot approve their own disposal. Completion is rejected for non-ACTIVE assets, active custody, pending transfers, or active work orders. Domain validation failures use the standard API error envelope described above.

## Asset assurance and physical verification

The asset API accepts `condition` (`GOOD`, `FAIR`, `DAMAGED`, `CRITICAL`, or `UNKNOWN`) as the registered condition used during physical reconciliation. Existing assets migrate to `UNKNOWN` until an authorized asset manager records their condition.

- `GET/POST /api/v1/verification/campaigns/` lists campaigns or creates a DRAFT campaign with `name`, `scope_type` (`ORGANIZATION`, `DEPARTMENT`, `LOCATION`), `start_date`, optional `due_date`/`description`, and the applicable `department_id` or `location_id`.
- `GET/PATCH /api/v1/verification/campaigns/{id}/` retrieves or edits a draft. POST actions `/start/`, `/complete/`, `/cancel/`, and `/reconcile-missing/` open, complete, cancel, or record expected assets that were not found. Campaign responses include database-derived expected, verified, unverified, exception, resolved-exception, and percentage fields.
- `GET/POST /api/v1/verification/records/` lists or creates observations. Input includes `campaign_id`, optional `asset_id` (omit for an unregistered physical item), observed tag/description/location/department/custodian/condition, and notes. Result, verifier, timestamp, organization, and generated exceptions are server-controlled. `GET /api/v1/verification/records/{id}/` retrieves a record; observations have no update/delete endpoint.
- `GET/POST /api/v1/verification/exceptions/` and `GET /api/v1/verification/exceptions/{id}/` list, retrieve, or create a reviewer-raised `OTHER` issue using `verification_id`, `description`, and optional `severity`. POST actions `/assign/` (`assigned_to_id`), `/start-review/`, `/resolve/`, `/accept/`, and `/reject/` operate the exception lifecycle. Closure actions accept `resolution_notes` and an optional `resolution_reference` for a separately completed workflow.
- `GET/POST /api/v1/verification/evidence/` lists or creates evidence. Input includes `verification_id`, optional `exception_id`, and `evidence_type`. Metadata-only legacy references may include `storage_key` or `external_reference`; NOTE evidence may omit references. Multipart uploads are limited by `EVIDENCE_MAX_UPLOAD_BYTES` (20 MiB default); actual bytes determine the PDF/JPEG/PNG candidate type and undergo bounded structural validation. PDF validation currently supports classic xref tables only; xref-stream PDFs fail closed. SHA-256 is recorded after storage read-back verification. The caller's filename is display metadata only. `GET /api/v1/verification/evidence/{id}/content/` retrieves a verified binary as an attachment; storage keys are never returned. Legacy metadata remains `LEGACY_UNVERIFIED` and has no binary retrieval.

Campaign lists filter by status, scope type, department, and location. Observation lists filter by campaign, asset, observed department/location/custodian, result, condition, and verification date bounds; search includes tags, descriptions, and notes. Exception lists filter by campaign, asset, department, location, status, type, severity, and assignee. Evidence lists filter by verification, exception, and type. Lists use page-number pagination, search where applicable, and allow-listed ordering.

ADMIN and ASSET_MANAGER may manage campaigns, exceptions, and evidence. DEPARTMENT_MANAGER has scoped read access and may create observations only within their department. ACCOUNTANT has read access. EMPLOYEE has no access. All querysets and related input IDs are organization-scoped. Reconciliation preserves the asset register: changing physical location/custody still requires the existing transfer/assignment workflows. Organization, department, and location scope relationships are validated; foreign organization references return the standard validation error envelope.
# Asset assurance API

Assurance endpoints are available under `/api/v1/assurance/` and use the existing authenticated AssetFlow roles and organization scoping.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET`, `POST` | `/runs/` | List scoped runs or create a pending run (`run_type`, optional completed `verification_campaign_id`, optional positive `stale_after_days`). |
| `GET` | `/runs/{id}/` | Retrieve a run in the user's permitted scope. |
| `POST` | `/runs/{id}/execute/` | Execute or safely re-enter a pending/running run; completed runs return their existing result. |
| `POST` | `/runs/{id}/cancel/` | Cancel a pending run. |
| `GET` | `/runs/{id}/findings/` | List findings detected during a run. |
| `GET` | `/findings/`, `/findings/{id}/` | Search and filter durable findings. |
| `POST` | `/findings/{id}/review/` | Move an open finding into review. |
| `POST` | `/findings/{id}/resolve/`, `/accept/`, `/reject/` | Close an under-review finding; each requires `resolution_notes`. |
| `GET` | `/summary/` | Return role-scoped counts by severity, type, and status plus recurring/multi-finding totals. |

Run filters: `run_type`, `status`, and `verification_campaign`. Finding filters: `finding_type`, `severity`, `status`, `source`, `run`, `asset`, `department`, and `location`. Findings support text search over tag, name, type, description, expected value, and observed value, plus ordering on type, severity, status, source, detection timestamps, occurrence count, and creation time. List endpoints use the shared response format (`count`, `next`, `previous`, `results`) with `page` and `page_size` query parameters.

Run types are `FULL`, `PHYSICAL`, `FINANCIAL`, and `OPERATIONAL`. Physical runs require a completed verification campaign in the same organization. Repeating execution of a `COMPLETED` run returns the saved result without evaluating again. A `RUNNING` run can be re-entered after interrupted work; concurrent evaluators serialize on the run row, and finding changes commit atomically. A `FAILED` or `CANCELLED` run is terminal; create a new run to repeat a control after failure. Task dispatch occurs after transaction commit. M10.5 captures immutable input values without asset-population update locks, evaluates durable work units, and atomically publishes results after all units succeed. Read-only run metadata adds execution_phase, captured_at, sealed_at, executor_version, input_schema_version, population_count, unit_count and units_completed. Public statuses are unchanged. Transient failures use durable backoff and periodic redispatch; legacy RUNNING executions require operator review. See [execution and rollout details](../backend/assurance/README.md). Finding transitions are `OPEN → UNDER_REVIEW → RESOLVED|ACCEPTED|REJECTED`; the final states are immutable. Repeat detections update an active finding and append a per-run occurrence snapshot. A finding that reappears after closure is a new finding record.

Administrators and asset managers can create, execute, cancel, review, and close findings. Accountants can read financial runs and finding types. Department managers can read operational findings within their department and do not receive organization-wide run listings. Employees have no assurance access. Every query remains organization-scoped.

Evidence binaries are stored only through the explicit private `assetflow_private` Django storage alias; no public media URL is configured. Retrieval requires the evidence's organization and applicable department scope, verified integrity metadata, and an authenticated role. Responses use attachment disposition and `X-Content-Type-Options: nosniff`. Structural validation is not malware scanning, content disarm/reconstruction, or proof that a valid document is benign. Evidence is audit history and cannot be edited or deleted through the API.

## Reporting and point-in-time snapshots

- `GET /api/v1/reports/` returns the report catalog. Each entry contains `report_type`, `label`, `result_url`, `snapshot_supported`, `columns`, and the supported `filters` for that report.
- `GET /api/v1/reports/{report_type}/` returns current-state rows in the standard paginated envelope (`count`, `next`, `previous`, `results`). Supported filters vary by report and are listed by the catalog: `department`, `status`, `date_from`, `date_to`, `asset_tag`, and `search` where applicable.
- `POST /api/v1/report-snapshots/` accepts `report_type`, optional `filters`, and a caller-generated UUID `idempotency_key`. A new request returns `202 Accepted`; repeating the same key and parameters returns the same snapshot. A repeated queued request safely re-enqueues that snapshot ID.
- `GET /api/v1/report-snapshots/` lists snapshots in the standard paginated envelope. `GET /api/v1/report-snapshots/{id}/` returns status and metadata. `GET /api/v1/report-snapshots/{id}/rows/` returns completed rows in the standard paginated envelope; rows are unavailable until the snapshot completes.

Snapshot metadata fields are `id`, `report_type`, `parameters`, `scope_department_id`, `status`, `requested_at`, `started_at`, `as_of`, `generated_at`, `failed_at`, `row_count`, `summary`, `schema_version`, `failure_class`, and `failure_message`. Snapshot row entries contain `ordinal`, `source_id`, and `payload`. Decimal values in report rows and summaries are returned as exact strings.

Snapshots capture the selected current-state dataset in a PostgreSQL repeatable-read transaction. `as_of` records the capture transaction time. It does not request or imply reconstruction of prior mutable asset state. Financial rows use the existing asset book-value snapshots, posted depreciation entries, acquisition totals, and completed-disposal accounting snapshots; reports do not recalculate a ledger. Each snapshot is capped at 25,000 rows. Larger requests fail with a filter hint and can be narrowed before requesting a new snapshot.

- `POST /api/v1/report-exports/` accepts `source_snapshot_id`, `format` (`CSV` or `JSON`), and a UUID `idempotency_key`. Only completed snapshots visible to the caller can be exported. New requests return `202`; replaying the same key and parameters returns the same job, while conflicting parameters are rejected.
- `GET /api/v1/report-exports/` lists scoped export metadata. `GET /api/v1/report-exports/{id}/` retrieves metadata and status. `GET /api/v1/report-exports/{id}/download/` returns a completed, unexpired artifact as an attachment.

Exports read only the immutable `ReportSnapshotRow` dataset and preserve its captured order. Schema-version-1 column names and order are frozen in the backend exporter registry; unknown versions fail closed. CSV protects textual spreadsheet formula prefixes while leaving schema-typed numeric values, including negative Decimals, unchanged. JSON uses a compact stable envelope with a schema version, snapshot metadata, ordered columns, and ordered rows; Decimal values remain their exact captured strings. Export artifacts are private, SHA-256 verified, bounded by `REPORT_EXPORT_MAX_BYTES` (100 MiB default), and expire after `REPORT_EXPORT_RETENTION_DAYS` (30 days by default). Expiry blocks downloads immediately; asynchronous deletion from private storage is retryable and is not atomic with expiry. OpenAPI is generated by the project's existing drf-spectacular schema endpoint/command.

The report catalog and results are organization-scoped and role-scoped. Department managers are constrained to their department using the relevant domain's existing visibility rules. Accountants receive financial report types. Employees have no reporting access. Snapshot history and rows apply the same current authorization checks as live reports. Assurance snapshots are also limited to the request-time role scope; accountants only see assurance snapshots generated with their financial-only scope.

The M10.7 Airflow pipeline is an internal extraction process, not an API endpoint. It reads only completed report snapshots through a Django management command and publishes versioned organization-scoped JSONL to non-public analytics storage. See [the analytics contract](analytics.md).
