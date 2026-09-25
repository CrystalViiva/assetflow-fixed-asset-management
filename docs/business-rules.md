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
- `accumulated_depreciation` is maintained by future depreciation postings.
- `current_book_value` is a maintained carrying-amount snapshot for efficient reads. Future posting services must update it with accumulated depreciation and ledger entries; it is not independently editable through the asset API.
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
- `purchase_cost` is the asset's final capitalized cost basis after capitalization. `current_book_value` begins at that cost; depreciation is not posted in this milestone.
- After capitalization, the asset master API and admin lock the acquisition date, capitalization date, purchase cost, residual value, useful life, and depreciation method. Future accounting-policy revision workflows will own changes to those values.
- Acquisition creation, material updates, and capitalization write audit events in the same transaction as their corresponding database changes. The capitalization operation writes an asset event and an acquisition event.
- ADMIN and ASSET_MANAGER may manage and capitalize acquisitions. ACCOUNTANT has read access, DEPARTMENT_MANAGER is limited to their department's assets, and EMPLOYEE has no acquisition API access.
