# F13 — Live operational dashboard

## Source and freshness

The authenticated Django dashboard is a bounded PostgreSQL aggregation at `GET /api/v1/dashboard/metrics/`. It is generated from transactional domain tables on request. `as_of` is the server's operational calculation time; it is not a repeatable historical reconstruction or a promise that all independently aggregated tables were read in one database snapshot. Refresh and window refocus re-read the endpoint. The browser never aggregates the asset register or falls back to mock numbers.

F9 reports remain query/snapshot workflows. F13 does not consume an F9 snapshot for current operating status. M10.7 extraction and M10.8 Airflow/PySpark curated marts remain batch analytics infrastructure with their own run/watermark semantics; they are not exposed directly to this dashboard and were not altered.

## Scope and access

ADMIN, ASSET_MANAGER, ACCOUNTANT, and DEPARTMENT_MANAGER can read the endpoint. EMPLOYEE and users without an organization receive 403. A department manager must have a department; the endpoint applies that department to assets and asset-linked operational records before aggregation. Audit activity for that role is restricted to direct Asset events for assets in that department. Django derives organization and department from the authenticated user. UI role gating is only presentation.

## Measures

- **Registered assets** counts every Asset row, including draft, pending capitalization, currently held, and disposed rows.
- **Currently held assets** counts ACTIVE, IN_MAINTENANCE, TRANSFERRED (completed internal moves remain held by the organization), and IMPAIRED. DISPOSED, DRAFT, and PENDING_CAPITALIZATION are excluded.
- **Capitalized assets/cost/book value/accumulated depreciation** use currently held assets with a non-null `capitalization_date`. Capitalized cost uses the Asset master `purchase_cost` once. Book value and accumulated depreciation use each asset's latest posted `DepreciationEntry` closing book value and accumulated amount; for assets with no posted entries, book value falls back to capitalized cost and accumulated depreciation to zero. A stale query-friendly Asset balance snapshot does not override its ledger. Acquisition components are not summed a second time. Currency is the organization's base currency; the acquisition service enforces that currency at capitalization.
- **Disposed assets** is a separate lifecycle count. Disposed asset values are excluded from current portfolio money measures; no disposal proceeds or gain/loss are mixed into book value.
- **Status distribution** counts all registered Asset states. Category, department, and location distributions include only currently held capitalized assets; each has server-grouped asset count and exact book value.
- **Posted depreciation by accounting period** sums actual immutable DepreciationEntry amounts over the latest twelve calendar periods (including the current period), without filling missing months. Current-month posted depreciation uses the matching current calendar `AccountingPeriod` year/month. These are posted amounts, not projections.
- **Capitalizations by month** groups public `CAPITALIZED` Acquisition `total_cost` by its actual `capitalization_date` for the latest twelve months through today, including assets later disposed because the capitalized event remains part of activity history. It is capitalized acquisition cost, not cash spend or a historical balance. The asset-to-acquisition relation is one-to-one.
- **Maintenance** counts OPEN, ASSIGNED, and IN_PROGRESS WorkOrders; critical count is the subset with CRITICAL priority. Current-month maintenance cost sums actual `MaintenanceCost.total_cost` by `incurred_at` in the current calendar month. Maintenance plans do not create work orders here.
- **Transfers/disposals** are explicit workflow queue counts: REQUESTED/APPROVED transfers and PENDING_APPROVAL/APPROVED disposals. They are not inferred from an Asset status.
- **Controls** keep open/under-review VerificationException and active public AssuranceFinding counts separate. Assurance counts use the backend's OPEN/UNDER_REVIEW statuses; internal candidates and occurrences are not used.
- **Recent activity** is a maximum of eight organization-scoped AuditLog events. Department managers see only direct Asset events for their department. Actor and timestamp come from the event; no client-generated activity is used.

All backend money aggregates use Django/PostgreSQL Decimal values and are serialized as two-decimal strings. The DTO rejects numeric money, malformed timestamps, counts, grouping rows, or currencies. The React formatter uses BigInt for exact integer grouping and does no accounting arithmetic. Legitimate empty aggregates serialize as `0.00` and counts as `0`; there are no optional fabricated metrics.

## Query behavior and UI

Asset totals and each grouping are separate database aggregations, so joining one-to-many work orders, depreciation entries, events, or findings cannot multiply asset value. Queue counts and recent activity are bounded queries; time series are limited to twelve calendar months and recent activity to eight events. No query loads the complete asset register. The screen shows live KPI cards, status/category/department/location distributions, actual posted depreciation and capitalizations, workflow queues, separate control indicators, and audit activity with navigation to existing domain screens.

Query keys include authenticated user and session generation. Data uses TanStack Query with a 30-second stale window, explicit refresh, and focus refetch; no aggressive interval polling is used. Logout uses the existing session cache boundary. An API 403/error remains an error and never substitutes mock analytics. Mock mode continues to use the existing demonstration dashboard.

## Limitations

This operational view is current-state analytics, not a financial close report, an arbitrary historical reconstruction, real-time streaming, or an assurance engine. Per-role access policy is currently endpoint-wide for the four listed roles, with department-manager scoping; it does not dynamically calculate a capability matrix. Cost and book value are asset-level current snapshots, and impairments are represented by the existing asset state/book values rather than recomputed here. The dashboard does not produce monthly periods with no entries.

## Verification

`python scripts/f1-smoke.py --f13` creates a randomly named disposable PostgreSQL database only. It seeds two tenants, two department assets at exact cost/depreciation/book values, two current-period posted depreciation entries, two child work orders on one asset, department-manager and employee users, then exercises the TypeScript client through HTTP and Django. It proves 300.30 capitalized cost, 30.15 accumulated and current-period posted depreciation, 270.15 book value without join multiplication, department-scoped 100.10/90.05 totals, foreign-tenant exclusion, employee 403, and a post-read draft-asset mutation changing registered count from two to three while financial totals remain unchanged. The disposable database is dropped; the configured application database is not used.
