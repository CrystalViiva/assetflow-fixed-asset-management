# AssetFlow architecture

## Backend request flow

The API follows a layered Django REST Framework structure:

```text
HTTP request
  -> viewset and organization/role permission
  -> serializer (input and presentation)
  -> domain service (validation, transaction, audit)
  -> selector/query layer
  -> Django ORM and PostgreSQL constraints
```

Asset list and detail queries use selectors with `select_related` for organization, category, department, location, and audit attribution users. Asset and acquisition services are the integration boundary for lifecycle workflows. Acquisition and capitalization rules do not live in serializers or viewsets. Depreciation, transfers, maintenance, and disposal remain future modules.

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

## Acquisition and capitalization

An `Acquisition` stores vendor/invoice references, acquisition and capitalization dates, currency, and each directly attributable cost component. Its `total_cost` is calculated server-side from the Decimal components; a PostgreSQL check constraint keeps the stored total synchronized with that formula. One acquisition is currently associated with each asset.

`assets.services.acquisition` owns creation, financial edits, and capitalization. Capitalization locks the acquisition row and then its asset row, validates lifecycle/accounting preconditions, activates the asset, sets the asset's `purchase_cost` and opening `current_book_value` to the derived capitalized cost, and updates the acquisition state. The asset and acquisition audit events are written in the same transaction, so either all state and audit changes commit or none do. Repeated requests serialize on the row lock and the second request sees the capitalized state.

Currency codes use an explicit supported ISO 4217 choice set. Until exchange-rate capture and translation are implemented, the acquisition currency must match its organization's base currency; no implicit currency conversion occurs.
