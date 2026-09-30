import hashlib
import json
from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from django.core.files.storage import storages
from django.test import override_settings
from django.utils import timezone

import analytics.services as services
from analytics.contracts import CONTRACT_VERSION, ENVELOPE_FIELDS, SNAPSHOT_REPORT_TYPES
from analytics.models import (
    AnalyticsCheckpoint,
    AnalyticsPublication,
    AnalyticsRun,
    AnalyticsRunStatus,
)
from reporting.export_schemas import SCHEMA_V1
from reporting.models import ReportSnapshot, ReportSnapshotRow, ReportType, SnapshotStatus


def _row_payload(**overrides):
    payload = {field.name: "" for field in SCHEMA_V1["asset_register"]}
    payload.update(
        {
            "id": str(uuid4()),
            "asset_tag": "AN-001",
            "name": "Extractor sample",
            "purchase_cost": "123456789012345678.99",
            "accumulated_depreciation": "0.10",
            "current_book_value": "123456789012345678.89",
        }
    )
    payload.update(overrides)
    return payload


def _snapshot(
    user, *, generated_at=None, rows=None, snapshot_id=None, report_type="asset_register"
):
    captured_at = generated_at or timezone.now()
    snapshot = ReportSnapshot.objects.create(
        id=snapshot_id or uuid4(),
        organization=user.organization,
        requested_by=user,
        requested_role=user.role,
        report_type=report_type,
        idempotency_key=uuid4(),
        status=SnapshotStatus.COMPLETED,
        started_at=captured_at,
        as_of=captured_at,
        generated_at=captured_at,
        row_count=len(rows or []),
        schema_version=1,
    )
    for ordinal, payload in enumerate(rows or [], start=1):
        ReportSnapshotRow.objects.create(
            snapshot=snapshot,
            ordinal=ordinal,
            source_id=payload["id"],
            payload=payload,
        )
    return snapshot


def _publish(manager, report_type="asset_register", run_key="manual-1"):
    return services.extract_report_snapshot_dataset(
        organization_id=manager.organization_id,
        report_type=report_type,
        run_key=run_key,
    )


def _read_records(publication):
    with services.published_output(publication) as output:
        return [json.loads(line) for line in output.read().splitlines()]


@pytest.mark.django_db
def test_extraction_is_tenant_scoped_and_preserves_contract_and_decimal_strings(
    manager, other_organization, analytics_storage
):
    own = _snapshot(manager, rows=[_row_payload()])
    from accounts.models import User

    foreign_user = User.objects.create_user(
        "analytics-other@example.test",
        "test-only-password",
        organization=other_organization,
        role="ASSET_MANAGER",
    )
    _snapshot(foreign_user, rows=[_row_payload(asset_tag="FOREIGN")])

    publication = _publish(manager)
    records = _read_records(publication)
    row = next(record for record in records if record["record_kind"] == "row")

    assert publication.organization_id == manager.organization_id
    assert publication.dataset == "asset_register"
    assert publication.contract_version == CONTRACT_VERSION
    assert row["organization_id"] == str(manager.organization_id)
    assert row["source_snapshot_id"] == str(own.pk)
    assert tuple(row) == ENVELOPE_FIELDS
    assert row["payload"]["purchase_cost"] == "123456789012345678.99"
    assert isinstance(row["payload"]["purchase_cost"], str)
    assert all(record["organization_id"] == str(manager.organization_id) for record in records)


@pytest.mark.django_db
def test_same_timestamp_snapshots_order_by_stable_snapshot_id_and_row_ordinal(
    manager, analytics_storage
):
    captured = timezone.now()
    later_id = UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
    earlier_id = UUID("00000000-0000-0000-0000-000000000001")
    _snapshot(
        manager, generated_at=captured, snapshot_id=later_id, rows=[_row_payload(asset_tag="Z")]
    )
    _snapshot(
        manager, generated_at=captured, snapshot_id=earlier_id, rows=[_row_payload(asset_tag="A")]
    )

    publication = _publish(manager)
    records = _read_records(publication)

    assert [record["source_snapshot_id"] for record in records] == [
        str(earlier_id),
        str(earlier_id),
        str(later_id),
        str(later_id),
    ]
    checkpoint = AnalyticsCheckpoint.objects.get(
        organization=manager.organization, dataset="asset_register"
    )
    assert checkpoint.watermark_at == captured
    assert checkpoint.watermark_snapshot_id == later_id
    assert checkpoint.watermark_ordinal == 1


@pytest.mark.django_db
def test_duplicate_airflow_delivery_reuses_publication_and_output(manager, analytics_storage):
    _snapshot(manager, rows=[_row_payload()])

    first = _publish(manager, run_key="scheduled__2026-09-30T03:00:00+00:00")
    repeated = _publish(manager, run_key="scheduled__2026-09-30T03:00:00+00:00")

    assert repeated.pk == first.pk
    assert AnalyticsRun.objects.filter(organization=manager.organization).count() == 1
    assert AnalyticsPublication.objects.filter(organization=manager.organization).count() == 1
    assert (
        first.sha256
        == hashlib.sha256(
            storages["assetflow_analytics"].open(first.storage_key, "rb").read()
        ).hexdigest()
    )


@pytest.mark.django_db
def test_failed_before_stage_keeps_checkpoint_unadvanced(manager, analytics_storage, monkeypatch):
    _snapshot(manager, rows=[_row_payload()])

    def fail_stage(**kwargs):
        raise OSError("staging unavailable")

    monkeypatch.setattr(services, "_stage_output", fail_stage)
    with pytest.raises(OSError, match="staging unavailable"):
        _publish(manager)

    run = AnalyticsRun.objects.get(organization=manager.organization)
    checkpoint = AnalyticsCheckpoint.objects.get(organization=manager.organization)
    assert run.status == AnalyticsRunStatus.FAILED
    assert checkpoint.watermark_at is None
    assert checkpoint.watermark_snapshot_id is None
    assert checkpoint.active_attempt_token is None
    assert not AnalyticsPublication.objects.exists()


@pytest.mark.django_db
def test_failed_after_staging_removes_unpublished_object_and_preserves_checkpoint(
    manager, analytics_storage, monkeypatch
):
    _snapshot(manager, rows=[_row_payload()])

    def fail_publish(**kwargs):
        raise RuntimeError("publication transaction failed")

    monkeypatch.setattr(services, "_publish", fail_publish)
    with pytest.raises(RuntimeError, match="publication transaction failed"):
        _publish(manager)

    run = AnalyticsRun.objects.get(organization=manager.organization)
    checkpoint = AnalyticsCheckpoint.objects.get(organization=manager.organization)
    assert run.status == AnalyticsRunStatus.FAILED
    assert checkpoint.watermark_at is None
    assert not AnalyticsPublication.objects.exists()
    assert list(Path(analytics_storage).rglob("*.jsonl")) == []


@pytest.mark.django_db
def test_success_publishes_verified_output_before_advancing_checkpoint(manager, analytics_storage):
    snapshot = _snapshot(manager, rows=[_row_payload()])

    publication = _publish(manager)

    checkpoint = AnalyticsCheckpoint.objects.get(organization=manager.organization)
    run = publication.run
    assert (
        publication.sha256
        == hashlib.sha256(
            storages["assetflow_analytics"].open(publication.storage_key, "rb").read()
        ).hexdigest()
    )
    assert publication.byte_size > 0
    assert run.status == AnalyticsRunStatus.COMPLETED
    assert checkpoint.watermark_at == snapshot.generated_at
    assert checkpoint.watermark_snapshot_id == snapshot.pk
    assert checkpoint.watermark_ordinal == snapshot.row_count
    assert checkpoint.active_attempt_token is None
    assert publication.published_at is not None


@pytest.mark.django_db
def test_stale_attempt_cannot_publish_or_advance_checkpoint(manager, analytics_storage):
    first_run, checkpoint, first_token = services._claim(
        organization_id=manager.organization_id, report_type="asset_register", run_key="first"
    )
    second_run, checkpoint, second_token = services._claim(
        organization_id=manager.organization_id, report_type="asset_register", run_key="second"
    )

    first_run.refresh_from_db()
    assert first_run.status == AnalyticsRunStatus.SUPERSEDED
    assert checkpoint.active_attempt_token == second_token
    with pytest.raises(services.StaleAnalyticsAttempt):
        services._publish(
            run_id=first_run.pk,
            token=first_token,
            checkpoint_id=checkpoint.pk,
            high=None,
            stored_key="attempts/stale.jsonl",
            digest=hashlib.sha256(b"").hexdigest(),
            byte_size=0,
            row_count=0,
        )
    checkpoint.refresh_from_db()
    assert checkpoint.watermark_at is None
    assert checkpoint.active_attempt_token == second_token
    assert not AnalyticsPublication.objects.exists()
    assert second_run.status == AnalyticsRunStatus.RUNNING


@pytest.mark.django_db
def test_empty_incremental_batch_publishes_valid_empty_jsonl(manager, analytics_storage):
    publication = _publish(manager)

    assert publication.row_count == 0
    assert publication.byte_size == 0
    assert publication.sha256 == hashlib.sha256(b"").hexdigest()
    assert _read_records(publication) == []
    assert AnalyticsCheckpoint.objects.get(organization=manager.organization).watermark_at is None


@pytest.mark.django_db
def test_late_completed_snapshot_inside_overlap_is_replayed_with_stable_logical_id(
    manager, analytics_storage
):
    now = timezone.now()
    first = _snapshot(manager, generated_at=now - timedelta(hours=12), rows=[_row_payload()])
    _publish(manager, run_key="run-1")
    late = _snapshot(
        manager, generated_at=now - timedelta(hours=18), rows=[_row_payload(asset_tag="LATE")]
    )

    publication = _publish(manager, run_key="run-2")
    records = _read_records(publication)
    keys = {record["logical_record_id"] for record in records}

    assert f"{late.pk}:row:1" in keys
    assert f"{first.pk}:row:1" in keys
    checkpoint = AnalyticsCheckpoint.objects.get(organization=manager.organization)
    assert checkpoint.watermark_snapshot_id == first.pk


@pytest.mark.django_db
def test_record_limit_failure_does_not_publish_or_advance(manager, analytics_storage):
    _snapshot(manager, rows=[_row_payload()])

    with (
        override_settings(ANALYTICS_MAX_RECORDS_PER_RUN=1),
        pytest.raises(services.AnalyticsExtractionError, match="record limit"),
    ):
        _publish(manager)

    assert not AnalyticsPublication.objects.exists()
    assert AnalyticsCheckpoint.objects.get(organization=manager.organization).watermark_at is None


@pytest.mark.django_db
def test_snapshot_row_count_mismatch_never_publishes_a_partial_dataset(manager, analytics_storage):
    _snapshot(manager, rows=[_row_payload()])
    ReportSnapshot.objects.filter(organization=manager.organization).update(row_count=2)

    with pytest.raises(services.AnalyticsExtractionError, match="row count"):
        _publish(manager)

    assert not AnalyticsPublication.objects.exists()
    assert AnalyticsCheckpoint.objects.get(organization=manager.organization).watermark_at is None


@pytest.mark.django_db
def test_noncontiguous_snapshot_ordinals_do_not_advance_checkpoint(manager, analytics_storage):
    payload = _row_payload()
    captured_at = timezone.now()
    snapshot = ReportSnapshot.objects.create(
        organization=manager.organization,
        requested_by=manager,
        requested_role=manager.role,
        report_type="asset_register",
        idempotency_key=uuid4(),
        status=SnapshotStatus.COMPLETED,
        started_at=captured_at,
        as_of=captured_at,
        generated_at=captured_at,
        row_count=1,
        schema_version=1,
    )
    ReportSnapshotRow.objects.create(
        snapshot=snapshot, ordinal=3, source_id=payload["id"], payload=payload
    )

    with pytest.raises(services.AnalyticsExtractionError, match="ordinals"):
        _publish(manager)

    assert not AnalyticsPublication.objects.exists()
    assert AnalyticsCheckpoint.objects.get(organization=manager.organization).watermark_at is None


@pytest.mark.django_db
def test_contract_allowlist_excludes_storage_keys_and_rejects_unknown_report_types(
    manager, analytics_storage
):
    payload = _row_payload()
    payload["storage_key"] = "private/evidence/a-real-key"
    _snapshot(manager, rows=[payload])

    with pytest.raises(services.AnalyticsExtractionError, match="frozen schema"):
        _publish(manager)
    assert not AnalyticsPublication.objects.exists()
    assert set(SNAPSHOT_REPORT_TYPES) == set(ReportType.values)
    with pytest.raises(services.AnalyticsExtractionError, match="Unknown report"):
        services.extract_report_snapshot_dataset(
            organization_id=manager.organization_id,
            report_type="not_a_dataset",
            run_key="invalid",
        )


@pytest.mark.django_db
def test_late_overlap_outputs_are_stable_upserts_and_identical_timestamps_do_not_skip(
    manager, analytics_storage
):
    same_time = timezone.now()
    newest = UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
    older_uuid = UUID("00000000-0000-0000-0000-000000000002")
    _snapshot(
        manager, generated_at=same_time, snapshot_id=newest, rows=[_row_payload(asset_tag="N")]
    )
    _publish(manager, run_key="first-same-time")
    _snapshot(
        manager, generated_at=same_time, snapshot_id=older_uuid, rows=[_row_payload(asset_tag="O")]
    )

    second = _publish(manager, run_key="second-same-time")

    assert f"{older_uuid}:row:1" in {
        record["logical_record_id"] for record in _read_records(second)
    }
    checkpoint = AnalyticsCheckpoint.objects.get(organization=manager.organization)
    assert checkpoint.watermark_snapshot_id == newest


@pytest.mark.django_db
def test_failed_run_retry_rotates_fence_and_completes_same_logical_run(
    manager, analytics_storage, monkeypatch
):
    _snapshot(manager, rows=[_row_payload()])
    original_stage = services._stage_output

    monkeypatch.setattr(
        services,
        "_stage_output",
        lambda **kwargs: (_ for _ in ()).throw(OSError("temporary storage error")),
    )
    with pytest.raises(OSError):
        _publish(manager, run_key="retryable")
    failed = AnalyticsRun.objects.get(run_key="retryable")
    failed_token = failed.attempt_token
    monkeypatch.setattr(services, "_stage_output", original_stage)

    publication = _publish(manager, run_key="retryable")

    failed.refresh_from_db()
    assert publication.run_id == failed.pk
    assert failed.status == AnalyticsRunStatus.COMPLETED
    assert failed.attempt_count == 2
    assert failed.attempt_token != failed_token
    assert AnalyticsPublication.objects.filter(run=failed).count() == 1


@pytest.mark.django_db
def test_full_refresh_recovers_records_older_than_late_arrival_overlap(manager, analytics_storage):
    now = timezone.now()
    first = _snapshot(manager, generated_at=now - timedelta(days=10), rows=[_row_payload()])
    _publish(manager, run_key="initial")
    late = _snapshot(
        manager, generated_at=now - timedelta(days=12), rows=[_row_payload(asset_tag="OLD")]
    )

    publication = services.extract_report_snapshot_dataset(
        organization_id=manager.organization_id,
        report_type="asset_register",
        run_key="operator-full-replay",
        full_refresh=True,
    )

    logical_ids = {record["logical_record_id"] for record in _read_records(publication)}
    assert f"{first.pk}:row:1" in logical_ids
    assert f"{late.pk}:row:1" in logical_ids
    assert publication.run.full_refresh is True
