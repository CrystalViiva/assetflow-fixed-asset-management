"""Frozen serializers for immutable M10.4 report snapshot schemas.

Do not import live report definitions here. A snapshot's schema version selects
the exact field order and CSV typing captured at that release.
"""

from dataclasses import dataclass

EXPORT_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ExportField:
    name: str
    kind: str = "text"


def _fields(names, decimals=(), integers=(), booleans=()):
    decimal_fields = set(decimals)
    integer_fields = set(integers)
    boolean_fields = set(booleans)
    return tuple(
        ExportField(
            name,
            "decimal"
            if name in decimal_fields
            else "integer"
            if name in integer_fields
            else "boolean"
            if name in boolean_fields
            else "text",
        )
        for name in names.split()
    )


# These field lists and types are the immutable schema-version-1 contract. The
# ordering matches the M10.4 ReportDefinition.fields insertion order.
SCHEMA_V1 = {
    "asset_register": _fields(
        "id asset_tag name status condition category department department_id location "
        "purchase_cost "
        "accumulated_depreciation current_book_value capitalization_date available_for_use_date",
        decimals=("purchase_cost", "accumulated_depreciation", "current_book_value"),
    ),
    "acquisitions": _fields(
        "id asset_tag asset_name department department_id vendor_name invoice_number "
        "acquisition_date capitalization_date currency purchase_price freight_cost "
        "installation_cost civil_works_cost "
        "other_capitalizable_cost total_cost status",
        decimals=(
            "purchase_price",
            "freight_cost",
            "installation_cost",
            "civil_works_cost",
            "other_capitalizable_cost",
            "total_cost",
        ),
    ),
    "depreciation": _fields(
        "id asset_tag department department_id year month opening_book_value depreciation_amount "
        "accumulated_depreciation closing_book_value posted_at",
        decimals=(
            "opening_book_value",
            "depreciation_amount",
            "accumulated_depreciation",
            "closing_book_value",
        ),
        integers=("year", "month"),
    ),
    "accounting_periods": _fields(
        "id year month status opened_at closed_at", integers=("year", "month")
    ),
    "assignments": _fields(
        "id asset_tag asset_name assigned_to department department_id location assigned_at "
        "returned_at"
    ),
    "transfers": _fields(
        "id asset_tag status from_department from_department_id to_department to_department_id "
        "from_location to_location requested_at completed_at reason"
    ),
    "work_orders": _fields(
        "id work_order_number asset_tag department department_id maintenance_type priority status "
        "due_date opened_at completed_at"
    ),
    "maintenance_costs": _fields(
        "id work_order_number asset_tag department department_id cost_type quantity unit_cost "
        "total_cost incurred_at",
        decimals=("quantity", "unit_cost", "total_cost"),
    ),
    "maintenance_records": _fields(
        "id asset_tag department department_id maintenance_type maintenance_date total_cost",
        decimals=("total_cost",),
    ),
    "disposals": _fields(
        "id asset_tag department department_id disposal_date disposal_method status currency "
        "proceeds "
        "capitalized_cost_at_disposal accumulated_depreciation_at_disposal carrying_amount "
        "gain_or_loss completed_at",
        decimals=(
            "proceeds",
            "capitalized_cost_at_disposal",
            "accumulated_depreciation_at_disposal",
            "carrying_amount",
            "gain_or_loss",
        ),
    ),
    "verification_campaigns": _fields(
        "id name status scope_type department department_id location start_date due_date "
        "completed_at"
    ),
    "verification_records": _fields(
        "id campaign asset_tag observed_asset_tag result observed_condition observed_department "
        "observed_department_id observed_location verified_at"
    ),
    "verification_exceptions": _fields(
        "id campaign asset_tag department department_id exception_type severity status created_at "
        "resolved_at"
    ),
    "assurance_runs": _fields(
        "id run_type status scheduled_for started_at completed_at assets_evaluated "
        "findings_generated findings_open findings_resolved",
        integers=("assets_evaluated", "findings_generated", "findings_open", "findings_resolved"),
    ),
    "assurance_findings": _fields(
        "id asset_tag finding_type severity status source occurrence_count first_detected_at "
        "last_detected_at",
        integers=("occurrence_count",),
    ),
    "assurance_occurrences": _fields(
        "id finding_id asset_tag finding_type severity run_id detected_at description"
    ),
    "lifecycle_history": _fields("id timestamp action entity_type entity_id user_email"),
}


def schema_for(snapshot):
    if snapshot.schema_version != EXPORT_SCHEMA_VERSION:
        raise ValueError(f"Unsupported report snapshot schema version: {snapshot.schema_version}")
    try:
        return SCHEMA_V1[snapshot.report_type]
    except KeyError as exc:
        raise ValueError("Unsupported report type for snapshot schema version 1.") from exc
