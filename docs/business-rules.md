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
- Status begins at DRAFT and is read-only on master-data APIs. Capitalization, maintenance, and disposal services own their supported transitions; `PENDING_CAPITALIZATION`, `TRANSFERRED`, and `IMPAIRED` do not currently have transitions that set them.
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
- For an ACTIVE asset, ordinary asset updates and assignment creation cannot change department or location. Approved transfer completion owns those placement changes. Draft placement may be edited before capitalization. A global superuser may make an audited correction in Django admin; tenant-scoped staff cannot edit active placement there.
- Transfers follow REQUESTED → APPROVED → COMPLETED, or REQUESTED → REJECTED/CANCELLED. Rejected and cancelled requests cannot be completed. Completed transfer history is immutable and cannot be deleted through the API or admin.
- Completion rechecks the asset's source snapshot while holding row locks. If another operation changed its placement after request, completion is rejected rather than overwriting newer state. Transfer movement does not rewrite the asset lifecycle status; `TRANSFERRED` remains a legacy/explicit lifecycle value and is not the transfer ledger.
- Assignments and transfers, including all referenced users, departments, locations, and assets, must belong to the same organization. API querysets and mutation services are organization-scoped; cross-organization IDs are rejected.
- Assignment creation/return and transfer request/approval/rejection/cancellation/completion run in database transactions. The asset row serializes assignment and movement changes; transfer transitions lock the transfer row, and completion then locks the asset. Audit events are recorded in the same transaction, so audit failure rolls back the domain operation.
- PostgreSQL enforces at most one active assignment per asset and at most one open transfer (REQUESTED or APPROVED) per asset. These uniqueness constraints protect races in addition to service validation and row locking.
- ADMIN and ASSET_MANAGER can manage assignments and transfers. ACCOUNTANT has organization-scoped read access. DEPARTMENT_MANAGER and EMPLOYEE have read-only access limited to their configured department or their currently assigned assets, respectively. All roles remain organization-isolated.

## Maintenance plans and work orders

- A `MaintenancePlan` stores an organization's intended preventive/inspection cadence, frequency unit, next due date, and instructions. It is configuration only: no scheduler, notifications, or automatic work-order generation is enabled. Inactive plans are retained; plans are not physically deleted. A disposed asset cannot have an active plan.
- A `WorkOrder` is the operational record while work is pending or underway. It moves OPEN → ASSIGNED → IN_PROGRESS → COMPLETED, with OPEN also permitted to move directly to IN_PROGRESS. Any nonterminal state may be cancelled. Completed and cancelled orders are terminal and immutable through supported interfaces.
- Work-order numbers are allocated from a per-organization database row protected with `select_for_update()` inside the creation transaction. The database also enforces organization-scoped number uniqueness. Sequence gaps are acceptable; collisions are not.
- Starting an order locks both work order and asset. An ACTIVE asset enters IN_MAINTENANCE; already-maintained, transferred, or impaired asset states are preserved. DRAFT, PENDING_CAPITALIZATION, and DISPOSED assets cannot receive or start work orders.
- Completion is atomic: it locks the order and asset, totals its recorded costs, creates one `MaintenanceRecord`, closes the work order, conditionally restores the asset to ACTIVE, and writes audit events. The asset returns from IN_MAINTENANCE only when no other ASSIGNED or IN_PROGRESS order remains. OPEN orders do not by themselves put an asset into maintenance.
- Cancelling a started order applies the same final-active-order check. Concurrent state transitions serialize on the asset row; repeated starts/completions re-check the locked work-order state. Audit failure rolls the entire operation back.
- A `MaintenanceRecord` is the permanent historical result produced when a work order completes. It snapshots asset, originating work order, maintenance date/type, summary, total recorded cost, downtime, and performer. Records and costs are retained and are not directly editable/deletable through the API/admin; corrections require a future controlled adjustment design.
- `MaintenanceCost` records labor, parts, service, or other expenditure against an active work order. Its `total_cost` is computed as quantity × unit cost using Decimal arithmetic and rounded to two currency decimals with ROUND_HALF_UP. Quantity must be positive and unit cost nonnegative; PostgreSQL checks the stored total against the rounded component product.
- Maintenance expenditure is an operating maintenance history measure. It does not change `Asset.purchase_cost`, `Asset.current_book_value`, or a depreciation schedule's capitalized basis. No maintenance cost is automatically capitalized.
- Custody assignments and department/location transfers remain independent of maintenance. Work-order actions do not change assignment history or asset location.
- ADMIN and ASSET_MANAGER can operate maintenance workflows. ACCOUNTANT, DEPARTMENT_MANAGER, and EMPLOYEE have read-only visibility; the latter two are limited to their department or currently assigned assets. Every query and mutation is organization-scoped.

## Disposal and derecognition

- A `Disposal` is an accounting workflow and permanent derecognition event. It is linked to the asset and organization; assets themselves are never physically deleted. Rejected/cancelled attempts remain available as workflow history, while the database permits at most one active disposal and one completed disposal per asset.
- Disposal methods are SALE, SCRAP, DONATION, WRITE_OFF, and TRANSFER_OUT. Proceeds are nonnegative Decimal amounts in the organization's base currency; zero proceeds are valid. Foreign exchange is not implemented.
- A disposal moves through DRAFT → PENDING_APPROVAL → APPROVED → COMPLETED, or through REJECTED/CANCELLED terminal paths. The requester cannot approve their own request. Only ACTIVE, capitalized assets may enter this workflow; other asset lifecycle states must be resolved through their own domain first.
- Completion locks the disposal and asset in one transaction and revalidates asset eligibility and accounting state. It is rejected while there is an active assignment, an open/requested or approved transfer, or an OPEN, ASSIGNED, or IN_PROGRESS work order. These histories are never silently closed or rewritten to permit derecognition.
- Carrying amount at derecognition is the persisted capitalized cost (`Asset.purchase_cost`) less posted accumulated depreciation. The result must agree with `Asset.current_book_value` and cannot fall below residual value. No missed depreciation is caught up and no depreciation, schedule, or accounting-period records are changed during disposal.
- Gain/(loss) is proceeds less carrying amount. Decimal arithmetic uses the project's two-decimal currency precision and `ROUND_HALF_UP` policy. The completed Disposal snapshots capitalized cost, accumulated depreciation, carrying amount, proceeds, and gain/(loss), so later asset changes cannot rewrite the historical calculation. Impairment is not modeled in this milestone.
- Completion sets the asset status to DISPOSED only after the snapshot and audit events are successfully written in the same transaction. Completed disposal accounting fields and all asset/lifecycle histories are retained; neither API nor admin exposes physical deletion or casual editing of a completed accounting event.
- ADMIN and ASSET_MANAGER can operate disposal workflows. ACCOUNTANT can read organization-scoped disposal/accounting data. DEPARTMENT_MANAGER reads disposals for their configured department; EMPLOYEE has no disposal access. All list and object access is organization-scoped.
- Audit events are recorded transactionally for creation, submission, approval, rejection, cancellation, derecognition, and completion. A failure to write audit data rolls back the workflow transition and asset state change.

## Asset assurance and physical verification

- The asset register stores a condition with an `UNKNOWN` default. Verification raises a condition mismatch when both the registered and observed conditions are known and differ; observed damage is also raised as its own exception. Physical verification never writes the asset condition.
- A `VerificationCampaign` defines an organization, department, or location scope by query; it does not copy asset master rows. Campaigns progress DRAFT → OPEN → IN_PROGRESS → COMPLETED, with cancellation allowed before completion. Verification records can be entered only while a campaign is open or in progress.
- The expected population is capitalized assets in ACTIVE, IN_MAINTENANCE, TRANSFERRED, or IMPAIRED state. DRAFT, PENDING_CAPITALIZATION, and DISPOSED assets are excluded. A disposed asset may still be observed and reconciled historically, but it does not inflate current expected-population metrics.
- `PhysicalVerification` preserves what a verifier observed, including tag, location, department, custodian, condition, and description. These facts cannot be edited after creation. Its `result` is a derived primary summary, so reconciliation may update it when later evidence (such as a duplicate tag) changes the summary; each such change is performed by a transactional service and written to the audit log. A linked registered asset is compared with its authoritative master record and current active `AssetAssignment`; an unregistered physical item is stored without an Asset row. A separate campaign reconciliation command records expected assets that were not located as ASSET_NOT_FOUND.
- Observations never update Asset department, location, custodian, lifecycle status, acquisition values, depreciation, or carrying amount. A discrepancy must be resolved through its owning workflow: transfer for location/department movement, assignment for custody, maintenance for condition, or disposal for derecognition. No workflow is created automatically.
- Reconciliation creates persistent exceptions for location, department, custody, tag, lifecycle, condition, missing, unregistered, and duplicate-tag discrepancies. Asset managers may also raise an `OTHER` exception against an open campaign observation. The verification `result` is a derived primary summary; all simultaneous discrepancies remain individually represented as exception records. Duplicate observed tags create exceptions for each conflicting observation without changing the captured observations.
- One verification per registered asset per campaign is enforced by a PostgreSQL uniqueness constraint. Unregistered observations may be repeated, while duplicate tags are explicitly detected within the campaign. An asset-not-found reconciliation record is linked to the expected asset but contains no physical observation values.
- Exceptions move OPEN → UNDER_REVIEW → RESOLVED, ACCEPTED, or REJECTED. Assignment, review, and closure are service-layer transitions; resolution records actor, time, notes, and an optional reference to a separately completed domain workflow. Exceptions and evidence metadata are retained.
- Evidence stores metadata and a storage key or external reference (except NOTE evidence). AssetFlow does not upload or store the binary file in this milestone; an object-storage integration is future work.
- Campaign progress is calculated in database queries: expected assets, found expected assets, unverified assets, exceptions, exceptions in RESOLVED state, and completion percentage. An asset-not-found row remains unverified; unregistered findings do not count as verification of an expected asset. ACCEPTED and REJECTED exceptions are terminal but are not counted as RESOLVED.
- Organization and department boundaries are enforced on campaign scope, linked assets, observations, assigned users, exceptions, and evidence. ADMIN/ASSET_MANAGER manage campaigns and exceptions; DEPARTMENT_MANAGER has scoped read access and can verify within their department; ACCOUNTANT has read access; EMPLOYEE has no assurance API access.
- Verification creation, discrepancy generation, campaign progress transitions, exception workflow changes, missing-asset reconciliation, and evidence metadata are audited transactionally. If exception or audit persistence fails, the associated operation rolls back. No physical inventory observation creates a transfer, assignment, maintenance order, or accounting entry implicitly.
# Asset assurance and reconciliation

Assurance runs are retained executions of a fixed set of deterministic controls. A run is created in `PENDING`, transitions to `RUNNING`, and ends in `COMPLETED` or `FAILED`; a pending run may be `CANCELLED`. Execution time, actor, selected physical verification campaign, population count, finding counts, and failure class are retained. The API dispatches eligible runs to Celery; the transition to `RUNNING` and its start audit event commit before task publication. The durable `AssuranceRun` is the source of execution state, not the Celery result. Evaluation findings and audit records are committed in one transaction. If evaluation fails, its finding writes roll back and the run is marked `FAILED` in a separate transaction.

The initial scheduled policy creates one `FULL` run per active organization per calendar day at 01:00 in the configured project timezone (default `Africa/Lagos`). `Organization.is_active` is the eligibility criterion. Celery Beat schedules orchestration only; it creates the durable run and calls the existing M10.1 dispatch path, which registers evaluation after transaction commit. `scheduled_for` identifies system-initiated runs, which have no fabricated user actor; creation and state changes remain audit logged with a null user and system metadata. A database uniqueness constraint on organization and scheduled date makes repeated orchestration for the same window idempotent. Run only one Celery Beat scheduler instance for this schedule. The `AssuranceRun` remains authoritative even when Celery redelivers either task.

Execution is safe for at-least-once task delivery: a repeated call for a `COMPLETED` run returns its existing result without evaluating it again. A `RUNNING` run may be re-entered after an interrupted evaluation; the service locks the run row for evaluation, so concurrent callers serialize, and the evaluation transaction either commits all findings/occurrences and completion or rolls all of them back. The stable run ID plus the unique finding/run occurrence constraint prevent duplicate occurrences. A `FAILED` or `CANCELLED` run is terminal and cannot be retried in place; create a new run after a recorded failure. The Celery task uses the run's stored `started_by` actor for audit attribution and does not automatically retry terminal validation failures.

The current evaluator materializes and locks the complete organization or campaign population in one transaction because duplicate-tag and other rules require cross-asset context. This bounds each run to one organization and its applicable campaign population, but does not impose a numeric asset cap. Chunking is deferred until a consistent run snapshot and global deduplication boundary are designed. Background work is registered with `transaction.on_commit()`, so a rolled-back dispatch cannot enqueue a task.

`FULL` evaluates the organization's asset master against physical, operational, disposal, depreciation, book-value, evidence, and stale-record controls. `PHYSICAL` requires a completed verification campaign and evaluates assets in that campaign's expected population plus unregistered items observed there. `FINANCIAL` runs disposal, depreciation, and book-value controls. `OPERATIONAL` runs physical reconciliation, lifecycle, evidence, stale-record, and open-workflow controls. Campaign observations are limited to the selected campaign; unregistered items are only meaningful when a campaign is selected. Other run types without a selected campaign use the latest observation available at the run start time for the organization.

Findings keep expected and observed values as the control's comparison snapshot. Expected means the value asserted by authoritative AssetFlow records or the defined control; observed means the physical observation or calculated/recorded value compared with it. A discrepancy never edits an Asset, assignment, disposal, or depreciation entry. Registered-asset findings can retain their source physical observation. Unregistered-asset findings retain the physical verification record instead of inventing an Asset row.

An open finding is deduplicated by organization, subject identity, and finding type. A repeat updates the current finding's latest detection, current comparison, severity, last run, and occurrence count. Each detection is also retained as an immutable per-run occurrence. Closing a finding as resolved, accepted, or rejected makes it terminal and immutable. If the same issue appears again later, the service creates a new open finding so the closed history remains intact. A single subject can have one active finding of each type.

Physical controls compare the current asset location, department, assignment custodian, tag, and condition with the latest qualifying observation. Campaign coverage means membership in the campaign's expected population and no recorded verification for that registered asset in that campaign. Duplicate observed tags are scoped to observations in the same campaign (or, without a campaign, to the latest organization-scoped observations). High- or critical-severity verification exceptions require at least one evidence metadata row. Such a row records metadata only; it does not prove that a binary file was uploaded or retained.

Lifecycle and disposal controls compare the existing AssetFlow status fields with operational records. They report disposed assets with active assignments/work, completed disposal without a disposed asset, and a disposed asset without a completed disposal. Open workflow controls report requested/approved transfers, open/assigned/in-progress work orders, and draft/pending/approved disposals. These rules reuse each owning application's status choices and do not create a second lifecycle state machine.

Financial controls compare the asset's accumulated depreciation with posted depreciation entries and schedule basis/status, check whether active capitalized assets have a schedule, and calculate book value with `Decimal` using the depreciation engine's currency rounding. The book-value check is capitalized cost less accumulated depreciation, floored at the recorded residual value. It flags differences; it does not post adjustments or rewrite ledgers. The disposal check compares retained disposal snapshots to retained asset accounting balances. These controls are deterministic integrity checks and do not establish IFRS or IAS 16 compliance.

The stale-record threshold is an explicit positive `stale_after_days` parameter stored on each run; its default is 365 days. Staleness uses `Asset.updated_at` relative to the run start time. This is a configurable control threshold, not a claim that every asset must be reviewed annually.

User initiated run and finding services scope reads and writes to the acting user's organization. The system scheduler supplies the active organization explicitly to the same service-layer dispatch and execution path, which scopes each run and its asset population to that organization. Department managers can read operational findings for their department; accountants can read financial finding types and financial runs; administrators and asset managers can read and manage assurance records. Employees do not receive assurance API access. Database foreign keys, checks, indexes, and the partial unique constraint protect local integrity; cross-tenant relationships are validated by domain services/model validation.

Known limits: the first version evaluates the available current state and retained events, not a complete event-sourced lifecycle timeline. It can only identify depreciation activity after disposal when a posted entry timestamp is later than the disposal completion timestamp. Evidence is metadata only. No rule performs automatic correction, accounting adjustment, transfer, or anomaly detection.

## Audit log retention

Audit events are created by domain services in the same transaction as the operation they describe. Ordinary model saves/updates and queryset updates/deletes are rejected after creation. Deleting a user may clear the optional actor foreign key while preserving the event. This is application-level ORM immutability, not tamper-proof storage: database owners and direct SQL can still alter records.
