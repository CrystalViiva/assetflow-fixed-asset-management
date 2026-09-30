import csv
import hashlib
import io
import json
from datetime import timedelta
from uuid import uuid4

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import storages
from django.db import connection
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User, UserRole
from reporting.export_schemas import SCHEMA_V1
from reporting.exports import execute_export, open_export, request_export
from reporting.models import (
    ExportFormat,
    ExportStatus,
    ReportExport,
    ReportSnapshot,
    ReportSnapshotRow,
    ReportType,
    SnapshotStatus,
)
from reporting.selectors import DEFINITIONS


def _snapshot(user, *, report_type=ReportType.ASSET_REGISTER, rows=None, schema_version=1):
    now = timezone.now()
    snapshot = ReportSnapshot.objects.create(
        organization=user.organization,
        requested_by=user,
        requested_role=user.role,
        report_type=report_type,
        idempotency_key=uuid4(),
        status=SnapshotStatus.COMPLETED,
        started_at=now,
        as_of=now,
        generated_at=now,
        row_count=len(rows or []),
        schema_version=schema_version,
    )
    for index, payload in enumerate(rows or []):
        ReportSnapshotRow.objects.create(
            snapshot=snapshot, ordinal=index, source_id=str(index), payload=payload
        )
    return snapshot


def _asset_row(**values):
    payload = {field.name: "" for field in SCHEMA_V1[ReportType.ASSET_REGISTER]}
    payload.update(values)
    return payload


def _private_storage(tmp_path):
    return {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
        "assetflow_private": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
            "OPTIONS": {"location": str(tmp_path)},
        },
    }


@pytest.mark.django_db
def test_schema_v1_export_uses_frozen_columns_after_live_definition_changes(
    manager, tmp_path, monkeypatch
):
    snapshot = _snapshot(manager, rows=[_asset_row(id="a1", asset_tag="A-1", name="Table")])
    with override_settings(STORAGES=_private_storage(tmp_path)):
        export, _ = request_export(
            user=manager,
            snapshot_id=snapshot.pk,
            export_format=ExportFormat.CSV,
            idempotency_key=uuid4(),
        )
        import reporting.selectors

        monkeypatch.setattr(
            reporting.selectors,
            "DEFINITIONS",
            {
                ReportType.ASSET_REGISTER: type(
                    "LiveDefinition", (), {"fields": {"changed": "changed"}}
                )()
            },
        )
        monkeypatch.setattr(
            reporting.selectors,
            "report_queryset",
            lambda *args, **kwargs: pytest.fail("Export must not rerun a live report selector."),
        )
        completed = execute_export(export_id=export.pk)
        with storages["assetflow_private"].open(completed.storage_key, "rb") as artifact:
            contents = artifact.read().decode("utf-8")
    assert contents.splitlines()[0] == ",".join(
        field.name for field in SCHEMA_V1[ReportType.ASSET_REGISTER]
    )
    assert "changed" not in contents.splitlines()[0]
    assert completed.status == ExportStatus.COMPLETED


@pytest.mark.django_db
def test_frozen_v1_column_order_matches_the_m104_contract():
    assert set(SCHEMA_V1) == set(DEFINITIONS)
    for report_type, definition in DEFINITIONS.items():
        assert tuple(field.name for field in SCHEMA_V1[report_type]) == tuple(definition.fields)


@pytest.mark.django_db
def test_unknown_snapshot_schema_fails_closed(manager):
    snapshot = _snapshot(manager, schema_version=99)
    with pytest.raises(ValidationError, match="Unsupported report snapshot schema"):
        request_export(
            user=manager,
            snapshot_id=snapshot.pk,
            export_format=ExportFormat.JSON,
            idempotency_key=uuid4(),
        )


@pytest.mark.django_db
def test_csv_escapes_text_formula_but_preserves_negative_decimal(manager, tmp_path):
    snapshot = _snapshot(
        manager,
        rows=[
            _asset_row(
                id="1", asset_tag=' =HYPERLINK("x")', name="@formula", purchase_cost="-12.3400"
            )
        ],
    )
    with override_settings(STORAGES=_private_storage(tmp_path)):
        export, _ = request_export(
            user=manager,
            snapshot_id=snapshot.pk,
            export_format=ExportFormat.CSV,
            idempotency_key=uuid4(),
        )
        completed = execute_export(export_id=export.pk)
        with storages["assetflow_private"].open(completed.storage_key, "rb") as artifact:
            header, row = list(csv.reader(io.StringIO(artifact.read().decode("utf-8"))))
    values = dict(zip(header, row, strict=True))
    assert values["asset_tag"] == '\' =HYPERLINK("x")'
    assert values["name"] == "'@formula"
    assert values["purchase_cost"] == "-12.3400"


def test_csv_formula_guard_covers_text_prefixes_and_leading_whitespace():
    from reporting.exports import _csv_value

    for text in ("=1+1", "+1+1", "-cmd", "@SUM(A1)", "\t=1+1", "  +1+1"):
        assert _csv_value(text, "text").startswith("'")
    assert _csv_value("-12.3400", "decimal") == "-12.3400"


@pytest.mark.django_db
def test_json_envelope_is_versioned_ordered_and_decimal_strings_are_exact(manager, tmp_path):
    snapshot = _snapshot(manager, rows=[_asset_row(id="1", purchase_cost="-0.0100")])
    with override_settings(STORAGES=_private_storage(tmp_path)):
        export, _ = request_export(
            user=manager,
            snapshot_id=snapshot.pk,
            export_format=ExportFormat.JSON,
            idempotency_key=uuid4(),
        )
        completed = execute_export(export_id=export.pk)
        with storages["assetflow_private"].open(completed.storage_key, "rb") as artifact:
            raw = artifact.read()
    payload = json.loads(raw)
    assert list(payload) == ["schema_version", "snapshot", "columns", "rows"]
    assert payload["schema_version"] == 1
    assert payload["columns"] == [field.name for field in SCHEMA_V1[ReportType.ASSET_REGISTER]]
    assert payload["rows"][0]["purchase_cost"] == "-0.0100"
    assert list(payload["rows"][0]) == payload["columns"]
    assert completed.sha256 == hashlib.sha256(raw).hexdigest()
    assert completed.byte_size == len(raw)


@pytest.mark.django_db
def test_export_idempotency_and_conflict(manager):
    first = _snapshot(manager)
    second = _snapshot(manager, report_type=ReportType.ACQUISITIONS)
    key = uuid4()
    export, created = request_export(
        user=manager, snapshot_id=first.pk, export_format="CSV", idempotency_key=key
    )
    repeated, repeated_created = request_export(
        user=manager, snapshot_id=first.pk, export_format="CSV", idempotency_key=key
    )
    assert created and not repeated_created and repeated.pk == export.pk
    with pytest.raises(ValidationError, match="different export parameters"):
        request_export(
            user=manager, snapshot_id=second.pk, export_format="CSV", idempotency_key=key
        )
    with pytest.raises(ValidationError, match="cannot be deleted"):
        export.delete()
    with pytest.raises(ValidationError, match="cannot be deleted"):
        ReportExport.objects.filter(pk=export.pk).delete()


@pytest.mark.django_db
def test_expiry_denies_download_before_physical_cleanup(manager, tmp_path):
    snapshot = _snapshot(manager)
    with override_settings(STORAGES=_private_storage(tmp_path)):
        export, _ = request_export(
            user=manager, snapshot_id=snapshot.pk, export_format="JSON", idempotency_key=uuid4()
        )
        completed = execute_export(export_id=export.pk)
        key = completed.storage_key
        completed.expires_at = timezone.now() - timedelta(seconds=1)
        completed.save(update_fields=("expires_at",))
        client = APIClient()
        client.force_authenticate(manager)
        response = client.get(f"/api/v1/report-exports/{completed.pk}/download/")
        assert response.status_code == 410
        assert storages["assetflow_private"].exists(key)
        with pytest.raises(PermissionDenied):
            open_export(export=completed)


@pytest.mark.django_db
def test_other_organization_cannot_retrieve_export_metadata_or_bytes(
    manager, other_organization, tmp_path
):
    foreign = User.objects.create_user(
        "foreign-export@example.test",
        "test-only-password",
        organization=other_organization,
        role=UserRole.ASSET_MANAGER,
    )
    snapshot = _snapshot(foreign)
    with override_settings(STORAGES=_private_storage(tmp_path)):
        export, _ = request_export(
            user=foreign, snapshot_id=snapshot.pk, export_format="JSON", idempotency_key=uuid4()
        )
        execute_export(export_id=export.pk)
        client = APIClient()
        client.force_authenticate(manager)
        assert client.get(f"/api/v1/report-exports/{export.pk}/").status_code == 403
        assert client.get(f"/api/v1/report-exports/{export.pk}/download/").status_code == 403


@pytest.mark.django_db
def test_partial_artifact_is_not_published_after_storage_verification_failure(
    manager, tmp_path, monkeypatch
):
    snapshot = _snapshot(manager, rows=[_asset_row(id="1")])
    with override_settings(STORAGES=_private_storage(tmp_path)):
        export, _ = request_export(
            user=manager, snapshot_id=snapshot.pk, export_format="CSV", idempotency_key=uuid4()
        )
        import reporting.exports

        monkeypatch.setattr(
            reporting.exports,
            "_verify_export_storage",
            lambda *args: (_ for _ in ()).throw(OSError("test")),
        )
        from reporting.exports import ExportAttemptError

        with pytest.raises(ExportAttemptError):
            execute_export(export_id=export.pk)
        export.refresh_from_db()
        assert export.status == ExportStatus.QUEUED
        assert export.storage_key == ""
        assert not any(path.is_file() for path in tmp_path.rglob("*"))
        client = APIClient()
        client.force_authenticate(manager)
        assert client.get(f"/api/v1/report-exports/{export.pk}/download/").status_code == 410


@pytest.mark.django_db
def test_export_api_rejects_employee_and_lists_scoped_jobs(employee):
    client = APIClient()
    client.force_authenticate(employee)
    assert client.get("/api/v1/report-exports/").status_code == 403


@pytest.mark.django_db
def test_duplicate_delivery_is_harmless_and_transient_failure_can_retry(
    manager, tmp_path, monkeypatch
):
    snapshot = _snapshot(manager, rows=[_asset_row(id="1")])
    with override_settings(STORAGES=_private_storage(tmp_path)):
        export, _ = request_export(
            user=manager, snapshot_id=snapshot.pk, export_format="JSON", idempotency_key=uuid4()
        )
        import reporting.exports

        original = reporting.exports._verify_export_storage
        monkeypatch.setattr(
            reporting.exports,
            "_verify_export_storage",
            lambda *args: (_ for _ in ()).throw(OSError("temporary storage read failure")),
        )
        from reporting.exports import ExportAttemptError

        with pytest.raises(ExportAttemptError):
            execute_export(export_id=export.pk)
        export.refresh_from_db()
        assert export.status == ExportStatus.QUEUED
        monkeypatch.setattr(reporting.exports, "_verify_export_storage", original)
        completed = execute_export(export_id=export.pk)
        duplicate = execute_export(export_id=export.pk)
        assert completed.status == duplicate.status == ExportStatus.COMPLETED
        assert completed.sha256 == duplicate.sha256
        second, _ = request_export(
            user=manager,
            snapshot_id=snapshot.pk,
            export_format="JSON",
            idempotency_key=uuid4(),
        )
        regenerated = execute_export(export_id=second.pk)
        assert regenerated.sha256 == completed.sha256


@pytest.mark.django_db
def test_periodic_recovery_requeues_durable_queued_export(
    manager, monkeypatch, django_capture_on_commit_callbacks
):
    snapshot = _snapshot(manager)
    export, _ = request_export(
        user=manager, snapshot_id=snapshot.pk, export_format="CSV", idempotency_key=uuid4()
    )
    ReportExport.objects.filter(pk=export.pk).update(updated_at=timezone.now() - timedelta(hours=1))
    import reporting.exports

    dispatched = []
    monkeypatch.setattr(
        reporting.exports, "_enqueue_export", lambda export_id: dispatched.append(export_id)
    )
    with django_capture_on_commit_callbacks(execute=True):
        assert reporting.exports.recover_exports(older_than=timedelta(minutes=1)) == 1
    assert dispatched == [export.pk]


@pytest.mark.django_db
def test_interrupted_running_export_is_recovered_before_resuming(
    manager, monkeypatch, django_capture_on_commit_callbacks, tmp_path
):
    snapshot = _snapshot(manager, rows=[_asset_row(id="1")])
    export, _ = request_export(
        user=manager, snapshot_id=snapshot.pk, export_format="CSV", idempotency_key=uuid4()
    )
    ReportExport.objects.filter(pk=export.pk).update(
        status=ExportStatus.RUNNING,
        started_at=timezone.now(),
        updated_at=timezone.now() - timedelta(hours=1),
    )
    import reporting.exports

    assert execute_export(export_id=export.pk).status == ExportStatus.RUNNING
    dispatched = []
    monkeypatch.setattr(
        reporting.exports, "_enqueue_export", lambda export_id: dispatched.append(export_id)
    )
    with django_capture_on_commit_callbacks(execute=True):
        assert reporting.exports.recover_exports(older_than=timedelta(minutes=1)) == 1
    assert dispatched == [export.pk]
    with override_settings(STORAGES=_private_storage(tmp_path)):
        completed = execute_export(export_id=export.pk)
    assert completed.status == ExportStatus.COMPLETED


@pytest.mark.django_db
def test_celery_export_task_retries_transient_generation_errors(manager, monkeypatch):
    from reporting import tasks

    retry_calls = []

    def retry(*, exc, countdown):
        retry_calls.append((exc, countdown))
        raise RuntimeError("retry scheduled")

    monkeypatch.setattr(
        tasks, "execute_export", lambda **kwargs: (_ for _ in ()).throw(OSError("temporary"))
    )
    monkeypatch.setattr(tasks.generate_report_export, "retry", retry)
    with pytest.raises(RuntimeError, match="retry scheduled"):
        tasks.generate_report_export.run("export-id")
    assert len(retry_calls) == 1
    assert isinstance(retry_calls[0][0], OSError)
    assert retry_calls[0][1] == 1


@pytest.mark.django_db(transaction=True)
def test_storage_io_runs_outside_generation_transactions_and_failure_is_retryable(
    manager, tmp_path, monkeypatch
):
    from reporting import exports

    monkeypatch.setattr(exports, "_enqueue_export", lambda export_id: None)
    snapshot = _snapshot(manager, rows=[_asset_row(id="1", name='comma, quote " and\r\nline')])
    with override_settings(STORAGES=_private_storage(tmp_path)):
        export, _ = request_export(
            user=manager,
            snapshot_id=snapshot.pk,
            export_format="CSV",
            idempotency_key=uuid4(),
        )
        storage = storages["assetflow_private"]
        calls = []
        for method_name in ("save", "open", "delete"):
            original = getattr(storage, method_name)

            def checked(*args, _original=original, _method=method_name, **kwargs):
                assert not connection.in_atomic_block, f"storage {_method} called in atomic block"
                calls.append(_method)
                return _original(*args, **kwargs)

            monkeypatch.setattr(storage, method_name, checked)

        original_event = exports.record_event
        failed_once = False

        def fail_before_publication(**kwargs):
            nonlocal failed_once
            if kwargs.get("action") == "REPORT_EXPORT_COMPLETED" and not failed_once:
                failed_once = True
                raise OSError("simulated audit/database publication failure")
            return original_event(**kwargs)

        monkeypatch.setattr(exports, "record_event", fail_before_publication)
        with pytest.raises(exports.ExportAttemptError):
            execute_export(export_id=export.pk)
        export.refresh_from_db()
        assert export.status == ExportStatus.QUEUED
        assert export.storage_key == ""
        assert not any(path.is_file() for path in tmp_path.rglob("*"))

        monkeypatch.setattr(exports, "record_event", original_event)
        completed = execute_export(export_id=export.pk)
        assert completed.status == ExportStatus.COMPLETED
        with storage.open(completed.storage_key, "rb") as stored:
            published_bytes = stored.read()
        assert completed.byte_size == len(published_bytes)
        assert completed.sha256 == hashlib.sha256(published_bytes).hexdigest()
        assert {"save", "open", "delete"}.issubset(calls)
        parsed = list(csv.reader(io.StringIO(published_bytes.decode("utf-8"), newline="")))
        values = dict(zip(parsed[0], parsed[1], strict=True))
        assert values["name"] == 'comma, quote " and\r\nline'


@pytest.mark.django_db(transaction=True)
def test_unpublished_export_is_not_downloadable_and_stale_attempt_cannot_replace_or_delete(
    manager, tmp_path, monkeypatch
):
    from reporting import exports

    monkeypatch.setattr(exports, "_enqueue_export", lambda export_id: None)
    snapshot = _snapshot(manager, rows=[_asset_row(id="1")])
    with override_settings(STORAGES=_private_storage(tmp_path)):
        export, _ = request_export(
            user=manager,
            snapshot_id=snapshot.pk,
            export_format=ExportFormat.JSON,
            idempotency_key=uuid4(),
        )
        client = APIClient()
        client.force_authenticate(manager)
        storage = storages["assetflow_private"]
        original_verify = exports._verify_export_storage
        losing_keys = []
        winner_bytes = b"winning published artifact"
        winner_key = f"exports/{manager.organization_id}/{export.pk}/attempts/winner/json"

        def verify_then_publish_newer_attempt(storage, key, size, digest):
            original_verify(storage, key, size, digest)
            losing_keys.append(key)
            assert not connection.in_atomic_block
            assert client.get(f"/api/v1/report-exports/{export.pk}/download/").status_code == 410
            storage.save(winner_key, ContentFile(winner_bytes))
            ReportExport.objects.filter(pk=export.pk).update(
                status=ExportStatus.COMPLETED,
                generation_token=None,
                completed_at=timezone.now(),
                storage_key=winner_key,
                byte_size=len(winner_bytes),
                sha256=hashlib.sha256(winner_bytes).hexdigest(),
            )

        monkeypatch.setattr(exports, "_verify_export_storage", verify_then_publish_newer_attempt)
        completed = execute_export(export_id=export.pk)
        assert completed.status == ExportStatus.COMPLETED
        assert completed.storage_key == winner_key
        assert losing_keys
        assert storage.exists(winner_key)
        assert not storage.exists(losing_keys[0])
        with storage.open(winner_key, "rb") as stored:
            assert stored.read() == winner_bytes
        download = client.get(f"/api/v1/report-exports/{export.pk}/download/")
        assert download.status_code == 200
        assert b"".join(download.streaming_content) == winner_bytes


@pytest.mark.django_db
def test_cleanup_removes_stale_attempt_key_but_never_the_published_key(manager, tmp_path):
    from reporting.exports import cleanup_failed_exports

    snapshot = _snapshot(manager)
    with override_settings(STORAGES=_private_storage(tmp_path)):
        export, _ = request_export(
            user=manager,
            snapshot_id=snapshot.pk,
            export_format="JSON",
            idempotency_key=uuid4(),
        )
        storage = storages["assetflow_private"]
        published_key = "exports/published/current.json"
        stale_key = "exports/obsolete/stale.json"
        storage.save(published_key, ContentFile(b"published"))
        storage.save(stale_key, ContentFile(b"stale"))
        ReportExport.objects.filter(pk=export.pk).update(
            status=ExportStatus.COMPLETED,
            started_at=timezone.now(),
            completed_at=timezone.now(),
            storage_key=published_key,
            byte_size=len(b"published"),
            sha256=hashlib.sha256(b"published").hexdigest(),
            cleanup_storage_keys=[stale_key],
        )
        cleanup_failed_exports(export_id=export.pk)
        export.refresh_from_db()
        assert storage.exists(published_key)
        assert not storage.exists(stale_key)
        assert export.cleanup_storage_keys == []


@pytest.mark.django_db
@pytest.mark.parametrize(
    "rows", [[], [_asset_row(id=str(i), asset_tag=f"A-{i}") for i in range(80)]]
)
def test_json_zero_and_many_rows_are_valid_and_ordinally_ordered(manager, tmp_path, rows):
    snapshot = _snapshot(manager, rows=rows)
    with override_settings(STORAGES=_private_storage(tmp_path)):
        export, _ = request_export(
            user=manager,
            snapshot_id=snapshot.pk,
            export_format=ExportFormat.JSON,
            idempotency_key=uuid4(),
        )
        completed = execute_export(export_id=export.pk)
        with storages["assetflow_private"].open(completed.storage_key, "rb") as stored:
            body = stored.read()
    document = json.loads(body)
    assert document["rows"] == sorted(document["rows"], key=lambda row: int(row["id"]))
    assert len(document["rows"]) == len(rows)
