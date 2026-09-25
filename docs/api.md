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
