import json
from datetime import datetime, timezone
from decimal import Decimal

import pytest

pyspark = pytest.importorskip("pyspark")
from analytics.curated_contracts import CURATED_SCHEMAS
from assetflow_spark.transform import (
    _empty_source_rows,
    _parse_publication,
    _source_or_empty,
    build_curated_datasets,
    curated_schema,
)
from pyspark.errors import PySparkException
from pyspark.sql import SparkSession
from pyspark.sql import types as T
from reporting.export_schemas import SCHEMA_V1


@pytest.fixture(scope="session")
def spark():
    session = (
        SparkSession.builder.master("local[2]")
        .appName("assetflow-m10-8-tests")
        .config("spark.ui.enabled", "false")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.ansi.enabled", "true")
        .config("spark.sql.shuffle.partitions", "4")
        .getOrCreate()
    )
    session.sparkContext.setLogLevel("ERROR")
    yield session
    session.stop()


def _payload(report_type, **overrides):
    result = {field.name: "" for field in SCHEMA_V1[report_type]}
    result["id"] = "00000000-0000-0000-0000-000000000011"
    result.update(overrides)
    return result


def _envelope(org, report_type, snapshot_id, *, kind, ordinal=0, payload=None):
    return {
        "contract_version": 1,
        "dataset": f"{report_type}_snapshots_v1",
        "organization_id": org,
        "logical_record_id": (
            f"{snapshot_id}:snapshot"
            if kind == "snapshot"
            else f"{snapshot_id}:row:{ordinal}"
        ),
        "record_kind": kind,
        "source_snapshot_id": snapshot_id,
        "source_snapshot_schema_version": 1,
        "source_row_id": None if kind == "snapshot" else payload["id"],
        "source_ordinal": ordinal,
        "source_as_of": "2026-01-02T03:04:05+00:00",
        "source_generated_at": "2026-01-02T03:04:06+00:00",
        "extracted_at": "2026-01-02T03:04:07+00:00",
        "payload": payload
        if payload is not None
        else {"report_type": report_type, "schema_version": 1, "row_count": 1},
    }


def _publication_file(tmp_path, records, *, report_type="asset_register"):
    path = tmp_path / f"{report_type}.jsonl"
    path.write_text(
        "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in records)
    )
    return {"dataset": report_type, "path": path.as_uri(), "row_count": len(records)}


def test_contract_v1_is_explicit_and_exact_decimal_parses_without_double(
    spark, tmp_path
):
    org = "00000000-0000-0000-0000-000000000001"
    snapshot = "00000000-0000-0000-0000-000000000101"
    payload = _payload(
        "asset_register",
        asset_tag="A-1",
        name="Precision asset",
        status="ACTIVE",
        purchase_cost="123456789012345678.91",
        accumulated_depreciation="0.01",
        current_book_value="123456789012345678.90",
    )
    records = [
        _envelope(org, "asset_register", snapshot, kind="snapshot"),
        _envelope(
            org, "asset_register", snapshot, kind="row", ordinal=1, payload=payload
        ),
    ]
    frame = _parse_publication(spark, _publication_file(tmp_path, records), org)
    assert frame.count() == 1
    assert frame.first()["purchase_cost"] == Decimal("123456789012345678.91")
    assert frame.schema["purchase_cost"].dataType == T.DecimalType(28, 2)
    assert not any(
        isinstance(field.dataType, T.DoubleType) for field in frame.schema.fields
    )


@pytest.mark.parametrize(
    "change, expected",
    [
        (lambda row: row.update(contract_version=2), "contract version"),
        (
            lambda row: row.update(
                organization_id="00000000-0000-0000-0000-000000000002"
            ),
            "organization",
        ),
        (lambda row: row.update(dataset="assurance_runs_snapshots_v1"), "payload"),
        (
            lambda row: row["payload"].update(
                private_storage_key="private/evidence/key"
            ),
            "payload",
        ),
        (lambda row: row["payload"].update(purchase_cost="1e90"), "decimal"),
    ],
)
def test_contract_rejects_unsupported_tenant_schema_and_bad_financial_values(
    spark, tmp_path, change, expected
):
    org = "00000000-0000-0000-0000-000000000001"
    snapshot = "00000000-0000-0000-0000-000000000101"
    payload = _payload("asset_register", asset_tag="A-1", purchase_cost="12.34")
    row = _envelope(
        org, "asset_register", snapshot, kind="row", ordinal=1, payload=payload
    )
    change(row)
    records = [_envelope(org, "asset_register", snapshot, kind="snapshot"), row]
    with pytest.raises(Exception, match=expected):
        _parse_publication(spark, _publication_file(tmp_path, records), org)


def test_malformed_json_and_duplicate_logical_ids_fail_closed(spark, tmp_path):
    org = "00000000-0000-0000-0000-000000000001"
    snapshot = "00000000-0000-0000-0000-000000000101"
    malformed = tmp_path / "bad.jsonl"
    malformed.write_text('{"contract_version":1\n')
    with pytest.raises((PySparkException, ValueError)):
        _parse_publication(
            spark,
            {"dataset": "asset_register", "path": malformed.as_uri(), "row_count": 1},
            org,
        )
    row = _envelope(org, "asset_register", snapshot, kind="snapshot")
    path = _publication_file(tmp_path, [row, row])
    with pytest.raises(ValueError, match="Duplicate M10.7 logical"):
        _parse_publication(spark, path, org)


def test_overlap_across_incremental_publications_deduplicates_stable_records(
    spark, tmp_path
):
    org = "00000000-0000-0000-0000-000000000001"
    snapshot = "00000000-0000-0000-0000-000000000101"
    payload = _payload("asset_register", asset_tag="A-1", purchase_cost="12.34")
    records = [
        _envelope(org, "asset_register", snapshot, kind="snapshot"),
        _envelope(
            org, "asset_register", snapshot, kind="row", ordinal=1, payload=payload
        ),
    ]
    earlier = tmp_path / "earlier.jsonl"
    later = tmp_path / "later.jsonl"
    earlier.write_text(
        "".join(json.dumps(row) + "\n" for row in records), encoding="utf-8"
    )
    for row in records:
        row["extracted_at"] = "2026-01-03T03:04:07+00:00"
    later.write_text(
        "".join(json.dumps(row) + "\n" for row in records), encoding="utf-8"
    )
    publications = [
        {"dataset": "asset_register", "path": earlier.as_uri(), "row_count": 2},
        {"dataset": "asset_register", "path": later.as_uri(), "row_count": 2},
    ]
    rows = _source_or_empty(
        spark, {"asset_register": publications}, "asset_register", org
    )
    assert rows.count() == 1
    assert rows.first()["purchase_cost"] == Decimal("12.34")


def _source_row(spark, report_type, organization_id, record_id, **values):
    empty = _empty_source_rows(spark, report_type)
    row = {field.name: None for field in empty.schema.fields}
    row.update(
        {
            "organization_id": organization_id,
            "logical_record_id": f"{record_id}:row:1",
            "source_snapshot_id": "00000000-0000-0000-0000-000000000101",
            "source_ordinal": 1,
            "source_as_of": datetime(2026, 1, 2, tzinfo=timezone.utc),
            "source_generated_at": datetime(2026, 1, 2, tzinfo=timezone.utc),
            "source_record_id": record_id,
            "id": record_id,
        }
    )
    row.update(values)
    return spark.createDataFrame([row], schema=empty.schema)


def _empty_inputs(spark):
    return {name: _empty_source_rows(spark, name) for name in SCHEMA_V1}


def test_all_curated_marts_are_tenant_scoped_and_financially_exact(spark):
    org = "00000000-0000-0000-0000-000000000001"
    inputs = _empty_inputs(spark)
    inputs["asset_register"] = _source_row(
        spark,
        "asset_register",
        org,
        "asset-1",
        asset_tag="A-1",
        name="Asset one",
        status="ACTIVE",
        condition="GOOD",
        category="IT",
        department="Finance",
        department_id=17,
        location="HQ",
        purchase_cost=Decimal("123456789012345678.91"),
        accumulated_depreciation=Decimal("0.01"),
        current_book_value=Decimal("123456789012345678.90"),
        capitalization_date="2025-01-01",
        available_for_use_date="2025-01-01",
    )
    inputs["acquisitions"] = _source_row(
        spark,
        "acquisitions",
        org,
        "acq-1",
        asset_tag="A-1",
        acquisition_date="2024-12-30",
        currency="NGN",
        total_cost=Decimal("123456789012345678.91"),
    )
    inputs["depreciation"] = _source_row(
        spark,
        "depreciation",
        org,
        "dep-1",
        asset_tag="A-1",
        year=2026,
        month=1,
        opening_book_value=Decimal("123456789012345678.91"),
        depreciation_amount=Decimal("0.01"),
        accumulated_depreciation=Decimal("0.01"),
        closing_book_value=Decimal("123456789012345678.90"),
        posted_at="2026-01-31T12:00:00+00:00",
    )
    inputs["maintenance_costs"] = _source_row(
        spark,
        "maintenance_costs",
        org,
        "maint-cost-1",
        work_order_number="WO-1",
        asset_tag="A-1",
        cost_type="PARTS",
        quantity=Decimal("2.500000"),
        unit_cost=Decimal("3.25"),
        total_cost=Decimal("8.13"),
        incurred_at="2026-01-20T12:00:00+00:00",
    )
    inputs["disposals"] = _source_row(
        spark,
        "disposals",
        org,
        "disp-1",
        asset_tag="A-2",
        status="COMPLETED",
        proceeds=Decimal("5.00"),
        gain_or_loss=Decimal("-2.00"),
        completed_at="2026-01-21T12:00:00+00:00",
    )
    inputs["assurance_findings"] = _source_row(
        spark,
        "assurance_findings",
        org,
        "finding-1",
        asset_tag="A-1",
        finding_type="MISSING_DEPRECIATION",
        severity="CRITICAL",
        status="OPEN",
        source="SYSTEM",
        occurrence_count=2,
        last_detected_at="2026-01-22T12:00:00+00:00",
    )

    outputs = build_curated_datasets(spark, inputs, org, "a" * 64)
    assert set(outputs) == set(CURATED_SCHEMAS)
    financial = outputs["asset_financial_position"].first()
    assert financial["capitalized_cost"] == Decimal("123456789012345678.91")
    assert financial["acquisition_total_cost"] == Decimal("123456789012345678.91")
    summary = outputs["executive_asset_summary"].first()
    assert summary["capitalized_cost"] == Decimal("123456789012345678.91")
    assert summary["depreciation_expense_total"] == Decimal("0.01")
    assert summary["maintenance_cost_total"] == Decimal("8.13")
    assert summary["disposal_proceeds"] == Decimal("5.00")
    assert summary["open_assurance_findings"] == 1
    assert outputs["asset_lifecycle_events"].count() >= 4
    for frame in outputs.values():
        assert all(
            field.dataType.simpleString() != "double" for field in frame.schema.fields
        )
        assert {
            row.organization_id
            for row in frame.select("organization_id").distinct().limit(2).collect()
        } == {org}


def test_duplicate_join_keys_and_cross_tenant_rows_fail(spark):
    org = "00000000-0000-0000-0000-000000000001"
    other = "00000000-0000-0000-0000-000000000002"
    inputs = _empty_inputs(spark)
    inputs["asset_register"] = _source_row(
        spark,
        "asset_register",
        org,
        "asset-1",
        asset_tag="A-1",
        name="A",
        status="ACTIVE",
    )
    inputs["acquisitions"] = _source_row(
        spark, "acquisitions", org, "acq-1", asset_tag="A-1", total_cost=Decimal("1.00")
    ).unionByName(
        _source_row(
            spark,
            "acquisitions",
            org,
            "acq-2",
            asset_tag="A-1",
            total_cost=Decimal("1.00"),
        )
    )
    with pytest.raises(ValueError, match="not one-to-one"):
        build_curated_datasets(spark, inputs, org, "a" * 64)
    inputs["acquisitions"] = _empty_source_rows(spark, "acquisitions")
    inputs["asset_register"] = _source_row(
        spark,
        "asset_register",
        other,
        "asset-x",
        asset_tag="X",
        name="Foreign",
        status="ACTIVE",
    )
    with pytest.raises(ValueError, match="organization boundary"):
        build_curated_datasets(spark, inputs, org, "a" * 64)


def test_empty_tenant_batch_still_builds_a_zero_summary(spark):
    org = "00000000-0000-0000-0000-000000000001"
    outputs = build_curated_datasets(spark, _empty_inputs(spark), org, "b" * 64)
    assert outputs["asset_financial_position"].count() == 0
    summary = outputs["executive_asset_summary"].first()
    assert summary["organization_id"] == org
    assert summary["asset_count"] == 0
    assert summary["capitalized_cost"] == Decimal("0.00")


def test_parquet_output_keeps_decimal_and_organization_partition(spark, tmp_path):
    org = "00000000-0000-0000-0000-000000000001"
    inputs = _empty_inputs(spark)
    inputs["asset_register"] = _source_row(
        spark,
        "asset_register",
        org,
        "asset-1",
        asset_tag="A-1",
        name="Asset one",
        status="ACTIVE",
        purchase_cost=Decimal("999999999999999999.99"),
        accumulated_depreciation=Decimal("0.00"),
        current_book_value=Decimal("999999999999999999.99"),
    )
    output = build_curated_datasets(spark, inputs, org, "c" * 64)[
        "asset_financial_position"
    ]
    target = tmp_path / "asset_financial_position"
    output.coalesce(1).write.partitionBy("organization_id").parquet(target.as_uri())
    readback = spark.read.schema(curated_schema("asset_financial_position")).parquet(
        target.as_uri()
    )
    assert readback.first()["capitalized_cost"] == Decimal("999999999999999999.99")
    assert list(target.rglob("*.parquet"))
    assert any(
        f"organization_id={org}" in str(path) for path in target.rglob("*.parquet")
    )
    assert readback.schema["capitalized_cost"].dataType == T.DecimalType(28, 2)
