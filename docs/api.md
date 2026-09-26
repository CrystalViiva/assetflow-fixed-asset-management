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

List endpoints use page-number pagination with a default page size of 25. Clients may set `page_size` up to 100; larger requested values are capped.

## Asset master data

- `GET/POST /api/v1/assets/` list and create assets.
- `GET/PATCH/PUT /api/v1/assets/{id}/` retrieve or update an asset. Physical deletion is not exposed.
- `GET /api/v1/assets/by-tag/{asset_tag}/` retrieve an asset by its organization-scoped tag.
- `GET/POST /api/v1/assets/categories/` list or create categories.
- `GET/PATCH/PUT /api/v1/assets/categories/{id}/` retrieve or update a category. Physical deletion is not exposed.

Asset lists accept `status`, `category` (UUID) or the frontend-compatible `category__name`, `department` or `department__name`, `location` or `location__name`, `manufacturer`, `acquisition_date_after`, `acquisition_date_before`, `search`, and `ordering`. Search checks tag, name, serial/model number, manufacturer, and description. Ordering is limited to explicitly supported fields.

Asset payloads use domain names such as `asset_tag`, `purchase_cost`, and `current_book_value`. Related category, department, and location IDs are accepted as `category_id`, `department_id`, and `location_id`; responses include their names and codes. Organization ID and lifecycle/accounting snapshots are read-only. `current_book_value` and `accumulated_depreciation` are reserved for later posting services.

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
- `GET/POST /api/v1/verification/evidence/` lists or creates evidence metadata. Input includes `verification_id`, optional `exception_id`, `evidence_type`, descriptive/file metadata, and `storage_key` or `external_reference`. NOTE evidence may omit a storage reference. The endpoint does not upload binaries.

Campaign lists filter by status, scope type, department, and location. Observation lists filter by campaign, asset, observed department/location/custodian, result, condition, and verification date bounds; search includes tags, descriptions, and notes. Exception lists filter by campaign, asset, department, location, status, type, severity, and assignee. Evidence lists filter by verification, exception, and type. Lists use page-number pagination, search where applicable, and allow-listed ordering.

ADMIN and ASSET_MANAGER may manage campaigns, exceptions, and evidence. DEPARTMENT_MANAGER has scoped read access and may create observations only within their department. ACCOUNTANT has read access. EMPLOYEE has no access. All querysets and related input IDs are organization-scoped. Reconciliation preserves the asset register: changing physical location/custody still requires the existing transfer/assignment workflows. Organization, department, and location scope relationships are validated; foreign organization references return the standard validation error envelope.
