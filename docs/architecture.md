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

Asset list and detail queries use selectors with `select_related` for organization, category, department, location, and audit attribution users. Asset, acquisition, depreciation, transfer, maintenance, disposal, verification, and assurance services own their domain transitions. Accounting and reconciliation rules do not live in serializers or viewsets.

## Implemented domain modules

Milestones 1-9 provide organization and account management; asset master data; acquisition and capitalization; depreciation schedules, entries, and accounting periods; custody assignments and transfers; maintenance plans and work orders; disposal and derecognition; physical verification campaigns, observations, exceptions, and evidence metadata; and durable assurance runs, findings, and occurrence history.

The React frontend still uses its mock repository. The Django API and mock frontend have not yet been connected by a production adapter.

## Asset master data

`AssetCategory` belongs to an organization and carries default accounting-policy values. The category defaults are applied when an asset is created without an explicit useful life or depreciation method. The selected values are copied onto the asset, so a later category-default edit does not silently rewrite existing asset policy.

`Asset` has an organization-scoped asset tag and optional department and location. Its category is required. Purchase cost, residual value, useful life, and depreciation method are the current policy/master-data inputs. Accumulated depreciation and current book value are persisted state for efficient reads; the depreciation ledger is the historical accounting source of truth, and posting updates both snapshots atomically.

Assets are not physically deleted through the API or Django admin. Status changes belong to lifecycle services, so the master-data endpoint returns status but does not allow callers to set it. Categories use `PROTECT` on assets, preserving the policy reference used by historical assets.

## Organization isolation and permissions

Every asset/category queryset is scoped to the authenticated user's organization. Category, department, and location references are also checked against the asset organization in model validation and the service layer; serializer querysets provide an early API check. Foreign keys alone cannot enforce a same-organization relationship across tables.

ADMIN and ASSET_MANAGER can create and update asset master data. ACCOUNTANT can read organization assets. DEPARTMENT_MANAGER reads assets assigned to their configured department. EMPLOYEE reads active assets in their organization. Reads and writes outside the user's organization are unavailable. This is the initial asset-domain policy, not the final workflow-specific RBAC matrix.

## Persistence and audit

PostgreSQL is configured through `DATABASE_URL`. Scoped unique constraints protect category codes/names and asset tags under concurrent requests. Check constraints enforce nonnegative monetary values, residual value not exceeding purchase cost, positive useful life when present, and date ordering.

Asset creation and updates run in a database transaction with an audit record. If validation or audit persistence fails, the operation rolls back. Audit changes store before/after values for submitted master-data fields. Audit events are append-only through ordinary ORM saves, updates, and deletes; this application-level guard does not protect against direct SQL or privileged database-owner actions.

## Acquisition and capitalization

An `Acquisition` stores vendor/invoice references, acquisition and capitalization dates, currency, and each directly attributable cost component. Its `total_cost` is calculated server-side from the Decimal components; a PostgreSQL check constraint keeps the stored total synchronized with that formula. One acquisition is currently associated with each asset.

`assets.services.acquisition` owns creation, financial edits, and capitalization. Capitalization locks the acquisition row and then its asset row, validates lifecycle/accounting preconditions, activates the asset, sets the asset's `purchase_cost` and opening `current_book_value` to the derived capitalized cost, and updates the acquisition state. The asset and acquisition audit events are written in the same transaction, so either all state and audit changes commit or none do. Repeated requests serialize on the row lock and the second request sees the capitalized state.

Currency codes use an explicit supported ISO 4217 choice set. Until exchange-rate capture and translation are implemented, the acquisition currency must match its organization's base currency; no implicit currency conversion occurs.

## Depreciation ledger and accounting periods

`Asset.purchase_cost` remains the capitalized cost basis. Capitalization initializes `current_book_value` to that cost and `accumulated_depreciation` to zero. `available_for_use_date` defaults to capitalization date and determines schedule commencement. The monthly convention takes a full monthly amount for the calendar month containing that date, without day proration.

`DepreciationSchedule` snapshots capitalized cost, depreciable amount, residual value, useful life, method, and relevant dates. `AccountingPeriod` is an explicitly opened organization/year/month record. `DepreciationEntry` is protected ledger history and has a PostgreSQL uniqueness constraint on organization, asset, and period.

The posting service locks the period, asset, and schedule, verifies sequential posting, writes the entry, advances the asset balance snapshots, and records audit in one transaction. Posting after a gap is rejected; catch-up is not implicit. Closed periods reject entries. Schedule revisions and regeneration are deferred; this milestone allows one schedule per asset and refuses replacement.

## Transfers, maintenance, and disposal

Assignments retain custody episodes. Approved transfer completion is the authoritative workflow for active-asset department/location changes. Ordinary asset updates and assignment creation cannot change active asset placement; a global superuser may make an explicitly audited administrative correction through Django admin. Transfers do not rewrite custody or lifecycle status.

Maintenance work orders own operational maintenance transitions and retain completion records and cost history. Disposal completion snapshots the asset's carrying amount and proceeds, calculates gain/(loss), and changes lifecycle state transactionally. Neither maintenance nor disposal rewrites depreciation entries.

## Physical verification and assurance

Physical verification stores observations separately from the authoritative asset register. Reconciliation creates durable, deduplicated findings and per-run occurrences without automatically correcting assets or accounting records. Verification evidence is metadata only; binary uploads are not implemented.

Assurance rules are deterministic and organization-scoped. The API dispatches execution to Celery after it transactionally marks the durable `AssuranceRun` as `RUNNING` and records the start audit event. The task is registered with `transaction.on_commit()`, so a rolled-back dispatch does not enqueue work. The `AssuranceRun` remains the source of execution state; Celery results contain only a run ID, status, and counts. At-least-once task delivery is safe: a completed run is idempotently returned on redelivery, while a `RUNNING` run can be re-entered under its row lock after an interrupted evaluation because candidate writes are atomic. A failed or cancelled run is terminal; create a new run to repeat after a recorded failure. Current evaluation materializes and locks the full scoped population in one transaction to preserve cross-asset rule context. Future bounded execution must define a consistent run snapshot and preserve global candidate identity before chunking.

The Celery task invokes the existing assurance execution service and uses the run's stored `started_by` actor for completion or failure audit attribution. No scheduled jobs are implemented.

## Tenant and admin boundaries

API permissions, query selectors, and domain services scope reads and mutations to an organization. Django admin querysets and related account choices are also organization-scoped for non-superuser staff; superusers retain global access. Foreign keys do not by themselves guarantee same-organization relationships, so services and form validation remain responsible for those checks.
