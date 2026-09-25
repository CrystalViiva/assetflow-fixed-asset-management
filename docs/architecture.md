# AssetFlow architecture

## Backend request flow

The API follows a layered Django REST Framework structure:

```text
HTTP request
  -> viewset and organization/role permission
  -> serializer (input and presentation)
  -> asset service (domain validation, transaction, audit)
  -> selector/query layer
  -> Django ORM and PostgreSQL constraints
```

Asset list and detail queries use selectors with `select_related` for organization, category, department, location, and audit attribution users. The asset service is the integration boundary for future capitalization, depreciation, transfers, maintenance, and disposal workflows. Those workflows do not live in the asset serializer or viewset.

## Asset master data

`AssetCategory` belongs to an organization and carries default accounting-policy values. The category defaults are applied when an asset is created without an explicit useful life or depreciation method. The selected values are copied onto the asset, so a later category-default edit does not silently rewrite existing asset policy.

`Asset` has an organization-scoped asset tag and optional department and location. Its category is required. Purchase cost, residual value, useful life, and depreciation method are the current policy/master-data inputs. Accumulated depreciation and current book value are persisted state for efficient reads; later posting services must keep them synchronized with the depreciation ledger. The ledger, once implemented, is the historical accounting source of truth.

Assets are not physically deleted through the API or Django admin. Status changes belong to lifecycle services, so the master-data endpoint returns status but does not allow callers to set it. Categories use `PROTECT` on assets, preserving the policy reference used by historical assets.

## Organization isolation and permissions

Every asset/category queryset is scoped to the authenticated user's organization. Category, department, and location references are also checked against the asset organization in model validation and the service layer; serializer querysets provide an early API check. Foreign keys alone cannot enforce a same-organization relationship across tables.

ADMIN and ASSET_MANAGER can create and update asset master data. ACCOUNTANT can read organization assets. DEPARTMENT_MANAGER reads assets assigned to their configured department. EMPLOYEE reads active assets in their organization. Reads and writes outside the user's organization are unavailable. This is the initial asset-domain policy, not the final workflow-specific RBAC matrix.

## Persistence and audit

PostgreSQL is configured through `DATABASE_URL`. Scoped unique constraints protect category codes/names and asset tags under concurrent requests. Check constraints enforce nonnegative monetary values, residual value not exceeding purchase cost, positive useful life when present, and date ordering.

Asset creation and updates run in a database transaction with an audit record. If validation or audit persistence fails, the operation rolls back. Audit changes store before/after values for submitted master-data fields.
