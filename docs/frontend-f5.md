# F5 — Maintenance, Work Orders and Maintenance Costs

## Backend contract

Maintenance is a separate operational domain. `MaintenancePlan` belongs to one asset and stores maintenance type, positive frequency value/unit, next due date, active flag and instructions. Plans can be listed, retrieved, created and updated; deletion is rejected and plans should be deactivated. There is no scheduler that automatically creates work orders from a due plan.

Work orders belong to an organization and asset. Django allocates sequential per-organization `WO-000001` style identifiers while locking the sequence row. Types are `PREVENTIVE`, `CORRECTIVE`, `INSPECTION`, and `EMERGENCY`; priorities are `LOW`, `MEDIUM`, `HIGH`, and `CRITICAL`. Creation starts at `OPEN`. Explicit actions are `assign` (`OPEN` → `ASSIGNED`), `start` (`OPEN` or `ASSIGNED` → `IN_PROGRESS`), `complete` (`IN_PROGRESS` → `COMPLETED`) and `cancel` (any nonterminal state → `CANCELLED`). Completed and cancelled work orders are terminal and immutable. Services lock work orders and assets inside transactions. Start sets an eligible `ACTIVE` asset to `IN_MAINTENANCE`; completion/cancellation restores it to `ACTIVE` when no other active assigned/in-progress work remains. Other eligible lifecycle states are left to backend rules.

`MaintenanceCost` is an immutable row attached to a nonterminal work order. It stores type (`LABOR`, `PARTS`, `SERVICE`, `OTHER`), description, positive quantity (3 decimal places), nonnegative unit cost (2 places), vendor reference and incurred timestamp. Django calculates and stores the rounded two-decimal total. The API has no currency field. Costs may be added before or during work; they cannot be edited or deleted, and cannot be added after terminal status. Costs do not update asset acquisition or depreciation fields.

Completion creates exactly one immutable `MaintenanceRecord` transactionally with date, type, resolution/notes/description summary, summed backend cost, optional downtime and optional performer. The response includes both the updated work order and generated record. Completion does not post depreciation or capitalize costs.

## API access and frontend architecture

The APIs are `/assets/maintenance-plans/`, `/assets/work-orders/`, `/assets/maintenance-costs/`, and `/assets/maintenance-records/`. Lists use the shared page-number contract (`page`, `page_size`, `count`, `next`, `previous`, `results`). Work-order filters include asset, status, type, priority, assignee, due date and opened date bounds; search and ordering are backend supported. Plans filter asset/type/active/date and search/order. Costs filter work order/type and search/order. Records filter asset/type/date and search/order. The client provides work-order asset/status/type/priority/search filters and real pagination; plan/cost/history lists use the backend's first 100-row page.

Explicit DTO parsers validate UUIDs, enum values, nullable relations, dates and decimal strings. Query keys include authenticated user and session generation. Mutations use Django domain actions, disable automatic retries and guard concurrent submits. Active maintenance queries are invalidated after changes; asset queries are invalidated because start and finalization can change lifecycle status. Acquisition and depreciation caches are not invalidated. A stale session blocks stale callbacks and cache invalidation.

The screen handles uncertain API outcomes by invalidating active authoritative reads and asks users to check refreshed server state before repeating. Completion success returns and parses the server-generated record; React never synthesizes history. A lost completion response triggers direct work-order detail and asset-history reads; success is reported only when Django shows the completed state and a linked record. A lost creation response remains conservative: the scoped order list is invalidated and the user is told to inspect it before retrying. Cost writes have no server idempotency key; after a lost response users must inspect refreshed cost rows before retrying.

Backend permissions allow reads to authenticated organization users, with ADMIN/ASSET_MANAGER writes. Department managers are limited to their department; employees see assets currently assigned to them; other authorized roles see organization-scoped records. Serializers scope asset, user and work-order references to the authenticated organization, selectors scope list/detail access, and services derive organization from the actor and lock same-tenant references. The UI limits mutations to ADMIN/ASSET_MANAGER but always honors API 403 responses.

## UI and mock separation

The Django Maintenance screen has Work Orders, Plans and Completed History views, backend filters, page controls, plan management, work-order creation, assignment-to-self, start/cancel, cost entry and completion forms. The Asset Detail Maintenance tab reads asset plans, work orders, costs and records without per-work-order browser requests. Unsupported document/audit tabs remain marked pending. Counts and costs are not fabricated. Inline forms were chosen because type/status context and completion evidence remain visible during the action; the existing `LogMaintenanceModal` stays in mock mode only.

Mock mode continues using its demo maintenance repository and modal. Django routes the Maintenance screen and Asset Detail to the dedicated Django components; it does not call mock maintenance APIs or mix demo data with backend records.

## Accounting boundary

Maintenance operations must leave acquisition/capitalized cost, residual value, useful life, depreciation method, accumulated depreciation, book value and depreciation entries unchanged. Work-order start/completion may update lifecycle status only as described by Django. F5 adds an isolated PostgreSQL smoke that captures asset and depreciation state before the workflow, exercises creation/start/cost/completion through TypeScript and Django, refetches state, checks exact decimals, records, audit events and duplicate completion, then drops its randomly named disposable database.

## Validation command

`python scripts/f1-smoke.py --f5`

No backend code or migrations were changed for F5. Plan recurrence has no scheduler; completion cannot be reopened; the screen currently offers assignment to the acting manager rather than an assignee picker; paginated plan/cost/history tables do not yet expose page controls. These are integration limitations, not simulated behavior.
