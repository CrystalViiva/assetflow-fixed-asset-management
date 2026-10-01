import hashlib
import json
from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from django.core.files.base import ContentFile
from django.core.files.storage import storages
from django.utils import timezone

from analytics.contracts import CONTRACT_VERSION
from analytics.curated_contracts import CURATED_SCHEMAS, TRANSFORM_VERSION
from analytics.curated_processing import (
    CuratedProcessingError,
    StaleCuratedAttempt,
    _claim_processing_run,
    _latest_source_publications,
    _mark_processing_failure,
    fail_curated_run,
    prepare_curated_runs,
    publish_curated_run,
)
from analytics.models import (
    AnalyticsPublication,
    AnalyticsRun,
    AnalyticsRunStatus,
    CuratedProcessingRun,
    CuratedPublication,
    CuratedRunStatus,
)

pytestmark = pytest.mark.django_db


def _source(manager, analytics_storage, dataset="asset_register", *, row_count=1, version=1):
    organization_id = manager.organization_id
    key = f"staging/{organization_id}/{dataset}/v1/{uuid4()}.jsonl"
    raw = b'{"test":"source"}\n'
    storage = storages["assetflow_analytics"]
    key = storage.save(key, ContentFile(raw))
    now = timezone.now()
    run = AnalyticsRun.objects.create(
        organization=manager.organization,
        dataset=dataset,
        run_key=f"run-{uuid4()}",
        status=AnalyticsRunStatus.COMPLETED,
        finished_at=now,
    )
    return AnalyticsPublication.objects.create(
        run=run,
        organization=manager.organization,
        dataset=dataset,
        contract_version=version,
        storage_key=key,
        sha256=hashlib.sha256(raw).hexdigest(),
        byte_size=len(raw),
        row_count=row_count,
        published_at=now,
    )


def _source_descriptor_for_test(publication):
    return {
        "organization_id": str(publication.organization_id),
        "dataset": publication.dataset,
        "contract_version": publication.contract_version,
        "publication_id": str(publication.pk),
        "run_id": str(publication.run_id),
        "storage_key": publication.storage_key,
        "sha256": publication.sha256,
        "byte_size": publication.byte_size,
        "row_count": publication.row_count,
        "published_at": publication.published_at.isoformat(),
        "source_watermark_at": None,
    }


def _fake_spark_outputs(run, analytics_storage, *, corrupt_digest=False):
    storage = storages["assetflow_analytics"]
    root_key = f"curated/stg/o{UUID(str(run.organization_id)).hex}/a{run.attempt_token.hex}"
    root_path = Path(storage.path(root_key))
    rows = []
    for dataset, schema in sorted(CURATED_SCHEMAS.items()):
        relative = f"{dataset}/part-00000.parquet"
        path = root_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        content = f"fake-parquet-payload-{dataset}".encode()
        path.write_bytes(content)
        digest = hashlib.sha256(content).hexdigest()
        if corrupt_digest and dataset == "asset_financial_position":
            digest = "0" * 64
        rows.append(
            {
                "name": dataset,
                "organization_id": str(run.organization_id),
                "row_count": 0,
                "schema": [list(field) for field in schema],
                "files": [{"path": relative, "byte_size": len(content), "sha256": digest}],
            }
        )
    input_path = Path(storage.path(run.input_manifest_key))
    raw_input = input_path.read_bytes()
    manifest = {
        "contract_version": CONTRACT_VERSION,
        "transform_version": TRANSFORM_VERSION,
        "organization_id": str(run.organization_id),
        "processing_run_id": run.pk,
        "processing_key": run.processing_key,
        "attempt_token": str(run.attempt_token),
        "source_manifest_sha256": hashlib.sha256(raw_input).hexdigest(),
        "datasets": rows,
    }
    manifest_path = root_path / "_assetflow_manifest.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")))
    return manifest_path


def test_processing_sources_are_successful_versioned_and_tenant_scoped(
    manager, other_organization, analytics_storage
):
    own = _source(manager, analytics_storage)
    other_manager = type(
        "Org", (), {"organization_id": other_organization.pk, "organization": other_organization}
    )()
    foreign = _source(other_manager, analytics_storage)
    selected = _latest_source_publications()
    assert set(selected) == {str(manager.organization_id), str(other_organization.pk)}
    batch = prepare_curated_runs()
    assert {item["organization_id"] for item in batch} == {
        str(manager.organization_id),
        str(other_organization.pk),
    }
    own_manifest = json.loads(
        Path(
            next(item for item in batch if item["organization_id"] == str(manager.organization_id))[
                "input_manifest_path"
            ]
        ).read_text()
    )
    assert own_manifest["organization_id"] == str(manager.organization_id)
    assert [row["publication_id"] for row in own_manifest["sources"]] == [str(own.pk)]
    assert str(foreign.pk) not in {row["publication_id"] for row in own_manifest["sources"]}


def test_empty_latest_batch_falls_back_to_last_nonempty_contract_v1(manager, analytics_storage):
    prior = _source(manager, analytics_storage, row_count=3)
    empty = _source(manager, analytics_storage, row_count=0)
    AnalyticsPublication.objects.filter(pk=prior.pk).update(published_at=timezone.now())
    AnalyticsPublication.objects.filter(pk=empty.pk).update(published_at=timezone.now())
    selected = _latest_source_publications()[str(manager.organization_id)]["asset_register"]
    assert [publication.pk for publication in selected] == [prior.pk]


def test_input_manifest_selects_latest_nonempty_publication(manager, analytics_storage):
    first = _source(manager, analytics_storage, "asset_register")
    second = _source(manager, analytics_storage, "asset_register")
    AnalyticsPublication.objects.filter(pk=first.pk).update(
        published_at=second.published_at - timedelta(seconds=1)
    )
    batch = prepare_curated_runs()[0]
    run = CuratedProcessingRun.objects.get(pk=batch["run_id"])
    assert [row["publication_id"] for row in run.source_publications] == [
        str(second.pk),
    ]


def test_latest_unknown_contract_fails_closed(manager, analytics_storage):
    _source(manager, analytics_storage, version=2)
    with pytest.raises(CuratedProcessingError, match="unsupported contract"):
        _latest_source_publications()


def test_deterministic_input_key_and_attempt_fence(manager, analytics_storage):
    publication = _source(manager, analytics_storage)
    descriptor = {
        "organization_id": str(publication.organization_id),
        "dataset": publication.dataset,
        "contract_version": publication.contract_version,
        "publication_id": str(publication.pk),
        "run_id": str(publication.run_id),
        "storage_key": publication.storage_key,
        "sha256": publication.sha256,
        "byte_size": publication.byte_size,
        "row_count": publication.row_count,
        "published_at": publication.published_at.isoformat(),
        "source_watermark_at": None,
    }
    run, old_token = _claim_processing_run(
        organization_id=str(manager.organization_id), sources=[descriptor]
    )
    retried, new_token = _claim_processing_run(
        organization_id=str(manager.organization_id), sources=[descriptor]
    )
    assert retried.pk == run.pk
    assert new_token != old_token
    assert retried.attempt_count == 2
    _mark_processing_failure(run.pk, old_token, RuntimeError("stale"))
    retried.refresh_from_db()
    assert retried.status == CuratedRunStatus.RUNNING
    assert retried.attempt_token == new_token
    with pytest.raises(StaleCuratedAttempt):
        publish_curated_run(run_id=run.pk, attempt_token=old_token)


def test_newer_tenant_source_set_fences_an_older_inflight_run(manager, analytics_storage):
    first = _source(manager, analytics_storage)
    second = _source(manager, analytics_storage)
    old, old_token = _claim_processing_run(
        organization_id=str(manager.organization_id),
        sources=[_source_descriptor_for_test(first)],
    )
    newer, _ = _claim_processing_run(
        organization_id=str(manager.organization_id),
        sources=[_source_descriptor_for_test(second)],
    )
    old.refresh_from_db()
    assert old.status == CuratedRunStatus.FAILED
    assert newer.status == CuratedRunStatus.RUNNING
    with pytest.raises(StaleCuratedAttempt):
        publish_curated_run(run_id=old.pk, attempt_token=old_token)


def test_publish_is_attempt_fenced_idempotent_and_manifest_verified(manager, analytics_storage):
    _source(manager, analytics_storage)
    batch = prepare_curated_runs()[0]
    run = CuratedProcessingRun.objects.get(pk=batch["run_id"])
    _fake_spark_outputs(run, analytics_storage)
    publication = publish_curated_run(run_id=run.pk, attempt_token=batch["attempt_token"])
    repeated = publish_curated_run(run_id=run.pk, attempt_token=batch["attempt_token"])
    assert repeated.pk == publication.pk
    assert publication.organization_id == manager.organization_id
    assert (
        publication.manifest_sha256
        == hashlib.sha256(
            Path(storages["assetflow_analytics"].path(publication.manifest_key)).read_bytes()
        ).hexdigest()
    )
    run.refresh_from_db()
    assert run.status == CuratedRunStatus.COMPLETED
    assert CuratedPublication.objects.filter(run=run).count() == 1


def test_repeat_prepare_after_publication_does_not_reopen_completed_run(manager, analytics_storage):
    _source(manager, analytics_storage)
    batch = prepare_curated_runs()[0]
    run = CuratedProcessingRun.objects.get(pk=batch["run_id"])
    _fake_spark_outputs(run, analytics_storage)
    publish_curated_run(run_id=run.pk, attempt_token=batch["attempt_token"])
    assert prepare_curated_runs() == []
    run.refresh_from_db()
    assert run.status == CuratedRunStatus.COMPLETED
    assert CuratedPublication.objects.filter(run=run).count() == 1


def test_corrupt_staged_file_never_publishes(manager, analytics_storage):
    _source(manager, analytics_storage)
    batch = prepare_curated_runs()[0]
    run = CuratedProcessingRun.objects.get(pk=batch["run_id"])
    _fake_spark_outputs(run, analytics_storage, corrupt_digest=True)
    with pytest.raises(CuratedProcessingError, match="digest did not verify"):
        publish_curated_run(run_id=run.pk, attempt_token=batch["attempt_token"])
    assert not CuratedPublication.objects.exists()
    run.refresh_from_db()
    assert run.status == CuratedRunStatus.RUNNING


def test_terminal_spark_failure_is_recorded_only_for_current_attempt(manager, analytics_storage):
    _source(manager, analytics_storage)
    batch = prepare_curated_runs()[0]
    fail_curated_run(
        run_id=batch["run_id"], attempt_token=batch["attempt_token"], failure_class="RuntimeError"
    )
    run = CuratedProcessingRun.objects.get(pk=batch["run_id"])
    assert run.status == CuratedRunStatus.FAILED
    assert run.finished_at is not None
    assert run.failure_message != "RuntimeError"
