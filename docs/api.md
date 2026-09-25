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
