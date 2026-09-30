"""Pure-Python analytics contract constants shared with Airflow DAG parsing."""

CONTRACT_VERSION = 1

# Frozen M10.4 report identifiers. Keep this independent of Django setup so DAG
# parsing never imports application settings or touches PostgreSQL.
SNAPSHOT_REPORT_TYPES = (
    "asset_register",
    "acquisitions",
    "depreciation",
    "accounting_periods",
    "assignments",
    "transfers",
    "work_orders",
    "maintenance_costs",
    "maintenance_records",
    "disposals",
    "verification_campaigns",
    "verification_records",
    "verification_exceptions",
    "assurance_runs",
    "assurance_findings",
    "assurance_occurrences",
    "lifecycle_history",
)

ENVELOPE_FIELDS = (
    "contract_version",
    "dataset",
    "organization_id",
    "logical_record_id",
    "record_kind",
    "source_snapshot_id",
    "source_snapshot_schema_version",
    "source_row_id",
    "source_ordinal",
    "source_as_of",
    "source_generated_at",
    "extracted_at",
    "payload",
)
