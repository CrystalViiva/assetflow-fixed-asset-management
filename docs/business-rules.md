# Asset master-data rules

This is an **IAS 16-aligned asset data foundation**, not a claim of full IAS 16 or IFRS compliance.

## Categories

- Each category belongs to one organization.
- Category code and name are unique within that organization.
- Category useful life must be positive, and capitalization threshold must be nonnegative.
- Straight Line, Reducing Balance, Units of Production, and Sum of Years' Digits are stored as policy choices. This milestone does not calculate depreciation using those methods.
- Useful life and depreciation method are defaults. On asset creation, defaults are copied into the asset only when the caller omits those values.

## Assets

- Asset tags are required and unique within an organization.
- A category is required. Department and location are optional, but when supplied they must belong to the same organization as the asset.
- Purchase cost and residual value are nonnegative, with residual value no greater than purchase cost.
- Useful life may be omitted for a draft; if present it must be greater than zero.
- Capitalization date cannot precede acquisition date.
- Current book value and accumulated depreciation cannot be negative.
- Status begins at DRAFT and is read-only on master-data APIs. Future lifecycle services will govern status transitions.
- Assets are not hard-deleted through the API or admin. Categories referenced by assets are protected from deletion.

## Financial field semantics

- `purchase_cost`, `residual_value`, `useful_life_months`, and `depreciation_method` hold asset-level accounting inputs; category values are only defaults. Before capitalization, a draft asset's purchase cost may be provisional; after capitalization it is the final capitalized cost basis.
- `available_for_use_date` determines depreciation commencement. Capitalization defaults it to the capitalization date when not explicitly set. It cannot precede capitalization.
- `accumulated_depreciation` is maintained by the depreciation posting service; posted entries are its historical ledger source.
- `current_book_value` is a maintained carrying-amount snapshot for efficient reads. Posting updates it with accumulated depreciation and ledger entries atomically; it is not independently editable through the asset API.
- Monetary values use decimal fields with two fractional digits. No floating-point accounting fields are used.

## Authorization and audit

- ADMIN and ASSET_MANAGER can create and update categories and asset master data.
- ACCOUNTANT has read access to organization-scoped assets and categories.
- DEPARTMENT_MANAGER reads assets for their configured department.
- EMPLOYEE reads active assets in their organization. Asset assignment-based visibility is deferred until the assignment domain exists.
- Asset creation and material master-data updates write an audit event in the same transaction as the asset change.

## Acquisition and capitalization

- An asset has one acquisition record in this milestone. The relationship is database-unique and protected from deletion.
- Acquisition cost components are `purchase_price + freight_cost + installation_cost + civil_works_cost + other_capitalizable_cost`. Each amount is a two-decimal `Decimal`; components cannot be negative and the total must be positive.
- `total_cost` is recomputed by the model and service and constrained in PostgreSQL to equal the sum of its components. API clients cannot set it as source data.
- Acquisition date is required. Capitalization date may be recorded later, but when present cannot precede acquisition date and is required to capitalize.
- Currency is an explicit ISO currency choice. The currently supported currency set includes NGN and other common currencies. Capitalization requires the acquisition currency to match the organization's base currency because foreign-exchange conversion is not implemented.
- A draft acquisition may only belong to an asset in the same organization. Only DRAFT or PENDING_CAPITALIZATION assets can be capitalized, and an asset with a capitalization date, depreciation balance, or existing carrying amount cannot be capitalized again.
- Capitalization locks the acquisition and asset rows in one transaction. It changes the acquisition to CAPITALIZED, the asset to ACTIVE, and sets asset purchase cost and initial current book value to the calculated capitalized cost. Residual value must not exceed that cost. If asset useful life is absent, the category default is copied to the asset.
- `purchase_cost` is the asset's final capitalized cost basis after capitalization. `current_book_value` begins at that cost, from which the depreciation ledger rolls forward.
- After capitalization, the asset master API and admin lock the acquisition date, capitalization date, available-for-use date, purchase cost, residual value, useful life, and depreciation method. Future accounting-policy revision workflows will own changes to those values.
- Acquisition creation, material updates, and capitalization write audit events in the same transaction as their corresponding database changes. The capitalization operation writes an asset event and an acquisition event.
- ADMIN and ASSET_MANAGER may manage and capitalize acquisitions. ACCOUNTANT has read access, DEPARTMENT_MANAGER is limited to their department's assets, and EMPLOYEE has no acquisition API access.

## Depreciation and accounting periods

- This milestone implements an **IAS 16-aligned straight-line depreciation foundation**; it does not claim IAS 16 or IFRS compliance. Only SLM is calculated. RBM, UOP, and SYD remain policy choices and schedule generation rejects them as unsupported.
- Depreciable amount is capitalized cost less residual value. Monthly SLM is the amount divided by useful life in months. Calculations use `Decimal`; current currency precision is two decimal places with `ROUND_HALF_UP` rounding.
- The monthly convention recognizes a full monthly amount for the calendar month containing the available-for-use date; daily proration is not applied. The schedule spans one period per useful-life month. A zero depreciable amount produces zero postings, keeping carrying amount at residual value.
- Posted amounts are capped at the remaining depreciable amount and carrying amount is floored at residual value. The final posting absorbs rounding remainder so accumulated depreciation reaches capitalized cost less residual value exactly.
- Accounting periods are explicitly opened for each organization/year/month. Periods are organization-unique and transition once from OPEN to CLOSED. Closed periods reject depreciation postings.
- Posting is sequential from the schedule start month. Missing periods are rejected rather than silently generated or caught up.
- A schedule snapshots its cost basis, depreciable amount, residual value, useful life, method, and dates. Ledger entries are protected history and database-unique per organization, asset, and period. Repeated posting does not double-count.
- Schedule generation and posting are service-layer operations. Posting locks the period, asset, and schedule and commits the entry, balance roll-forward, and audit event atomically. The asset snapshot must agree with the prior ledger closing balance or initial capitalized cost.
- ADMIN, ASSET_MANAGER, and ACCOUNTANT can administer depreciation. DEPARTMENT_MANAGER has read-only access to assets in their department; EMPLOYEE has no access. All queries and mutations are organization-scoped.
- Schedule revisions/regeneration, catch-up postings, alternate calculation engines, and disposal interactions are future decisions. This milestone rejects a second schedule rather than silently replacing one.

## Assignments and transfers

- An assignment is a custody episode: it records who is responsible for an asset and the department/location context at assignment time. `returned_at IS NULL` defines the single active assignment. An asset may have no active assignment, and unassigned custody is represented by a null `assigned_to`.
- Returning an assignment closes that episode and retains the record. Once closed, assignment history cannot be edited or deleted. Returning does not erase the asset's current department or location snapshot.
- A transfer records organizational or physical movement. It snapshots the asset's source department/location when requested and records a distinct destination. A destination must differ in at least one dimension.
- The asset's current `department` and `location` remain the current-state snapshot used for efficient filtering. Completing a transfer updates those fields; it does not automatically change employee custody or close an assignment. Custody changes must be made explicitly through the assignment workflow.
- Transfers follow REQUESTED → APPROVED → COMPLETED, or REQUESTED → REJECTED/CANCELLED. Rejected and cancelled requests cannot be completed. Completed transfer history is immutable and cannot be deleted through the API or admin.
- Completion rechecks the asset's source snapshot while holding row locks. If another operation changed its placement after request, completion is rejected rather than overwriting newer state. Transfer movement does not rewrite the asset lifecycle status; `TRANSFERRED` remains a legacy/explicit lifecycle value and is not the transfer ledger.
- Assignments and transfers, including all referenced users, departments, locations, and assets, must belong to the same organization. API querysets and mutation services are organization-scoped; cross-organization IDs are rejected.
- Assignment creation/return and transfer request/approval/rejection/cancellation/completion run in database transactions. The asset row serializes assignment and movement changes; transfer transitions lock the transfer row, and completion then locks the asset. Audit events are recorded in the same transaction, so audit failure rolls back the domain operation.
- PostgreSQL enforces at most one active assignment per asset and at most one open transfer (REQUESTED or APPROVED) per asset. These uniqueness constraints protect races in addition to service validation and row locking.
- ADMIN and ASSET_MANAGER can manage assignments and transfers. ACCOUNTANT has organization-scoped read access. DEPARTMENT_MANAGER and EMPLOYEE have read-only access limited to their configured department or their currently assigned assets, respectively. All roles remain organization-isolated.
