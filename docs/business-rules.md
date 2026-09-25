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

- `purchase_cost`, `residual_value`, `useful_life_months`, and `depreciation_method` hold asset-level accounting inputs; category values are only defaults.
- `accumulated_depreciation` is maintained by future depreciation postings.
- `current_book_value` is a maintained carrying-amount snapshot for efficient reads. Future posting services must update it with accumulated depreciation and ledger entries; it is not independently editable through the asset API.
- Monetary values use decimal fields with two fractional digits. No floating-point accounting fields are used.

## Authorization and audit

- ADMIN and ASSET_MANAGER can create and update categories and asset master data.
- ACCOUNTANT has read access to organization-scoped assets and categories.
- DEPARTMENT_MANAGER reads assets for their configured department.
- EMPLOYEE reads active assets in their organization. Asset assignment-based visibility is deferred until the assignment domain exists.
- Asset creation and material master-data updates write an audit event in the same transaction as the asset change.
