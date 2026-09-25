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
