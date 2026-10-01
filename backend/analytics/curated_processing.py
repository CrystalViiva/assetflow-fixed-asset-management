"""Claim and publish tenant-scoped M10.8 Spark attempts."""

import hashlib
import json
import logging
import uuid
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.files.storage import storages
from django.db import transaction
from django.utils import timezone

from analytics.contracts import CONTRACT_VERSION, SNAPSHOT_REPORT_TYPES
from analytics.curated_contracts import CURATED_SCHEMAS, REQUIRED_SOURCE_DATASETS, TRANSFORM_VERSION
from analytics.models import (
    AnalyticsPublication,
    AnalyticsRunStatus,
    CuratedProcessingRun,
    CuratedPublication,
    CuratedRunStatus,
)
from organizations.models import Organization

logger = logging.getLogger(__name__)
INPUT_PREFIX = "curated/input"
STAGING_PREFIX = "curated/stg"
MAX_MANIFEST_BYTES = 2 * 1024 * 1024
MAX_TENANTS_PER_DAG_RUN = 10_000


class CuratedProcessingError(Exception):
    """A source publication, Spark manifest or attempt failed validation."""


class StaleCuratedAttempt(CuratedProcessingError):
    """A newer fenced processing attempt owns this deterministic input set."""


def _canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def _storage():
    storage = storages["assetflow_analytics"]
    try:
        storage.path("")
    except (AttributeError, NotImplementedError) as exc:
        raise CuratedProcessingError(
            "M10.8 development Spark processing currently requires shared filesystem storage."
        ) from exc
    return storage


def _absolute_path(storage, key):
    root = Path(storage.path("")).resolve()
    path = Path(storage.path(key)).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise CuratedProcessingError("Analytics storage path escaped its configured root.") from exc
    return path


def _latest_source_publications():
    """Select each tenant/dataset's latest non-empty successful v1 publication."""
    ordering = ("organization_id", "dataset", "-published_at", "-pk")
    latest = (
        AnalyticsPublication.objects.select_related("run")
        .filter(run__status=AnalyticsRunStatus.COMPLETED)
        .order_by(*ordering)
        .distinct("organization_id", "dataset")
        .iterator(chunk_size=1000)
    )
    for publication in latest:
        if publication.contract_version != CONTRACT_VERSION:
            raise CuratedProcessingError(
                f"Latest published input for {publication.dataset} uses unsupported contract."
            )
    rows = (
        AnalyticsPublication.objects.select_related("run")
        .filter(
            run__status=AnalyticsRunStatus.COMPLETED,
            contract_version=CONTRACT_VERSION,
            row_count__gt=0,
        )
        .order_by(*ordering)
        .distinct("organization_id", "dataset")
        .iterator(chunk_size=1000)
    )
    by_organization = {}
    for publication in rows:
        organization_id = str(publication.organization_id)
        if (
            organization_id not in by_organization
            and len(by_organization) >= MAX_TENANTS_PER_DAG_RUN
        ):
            raise CuratedProcessingError("Tenant count exceeds the bounded Airflow mapping limit.")
        datasets = by_organization.setdefault(organization_id, {})
        datasets[publication.dataset] = [publication]
    return by_organization


def _source_descriptor(publication):
    if publication.dataset not in SNAPSHOT_REPORT_TYPES:
        raise CuratedProcessingError("Unexpected source dataset in analytics publication metadata.")
    if publication.run.organization_id != publication.organization_id:
        raise CuratedProcessingError("Source publication organization ownership is inconsistent.")
    if (
        publication.run.dataset != publication.dataset
        or publication.run.status != AnalyticsRunStatus.COMPLETED
    ):
        raise CuratedProcessingError(
            "Only completed matching analytics publications are consumable."
        )
    if publication.contract_version != CONTRACT_VERSION:
        raise CuratedProcessingError("Unsupported M10.7 analytics contract version.")
    if len(publication.sha256) != 64 or publication.byte_size < 0:
        raise CuratedProcessingError("Invalid source publication integrity metadata.")
    key = publication.storage_key.replace("\\", "/")
    if key.startswith("/") or any(part in {"", ".", ".."} for part in key.split("/")):
        raise CuratedProcessingError("Invalid source publication storage key.")
    return {
        "organization_id": str(publication.organization_id),
        "dataset": publication.dataset,
        "contract_version": publication.contract_version,
        "publication_id": str(publication.pk),
        "run_id": str(publication.run_id),
        "storage_key": key,
        "sha256": publication.sha256,
        "byte_size": publication.byte_size,
        "row_count": publication.row_count,
        "published_at": publication.published_at.isoformat(),
        "source_watermark_at": (
            publication.source_watermark_at.isoformat() if publication.source_watermark_at else None
        ),
    }


def _claim_processing_run(*, organization_id, sources):
    identity = {
        "organization_id": organization_id,
        "contract_version": CONTRACT_VERSION,
        "transform_version": TRANSFORM_VERSION,
        "sources": sources,
    }
    processing_key = hashlib.sha256(_canonical_json(identity)).hexdigest()
    token = uuid.uuid4()
    with transaction.atomic():
        # Serialize claims for a tenant even when the source publication set changes.
        Organization.objects.select_for_update().get(pk=organization_id)
        CuratedProcessingRun.objects.filter(
            organization_id=organization_id,
            status=CuratedRunStatus.RUNNING,
        ).exclude(processing_key=processing_key).update(
            status=CuratedRunStatus.FAILED,
            finished_at=timezone.now(),
            failure_class="SupersededAttempt",
            failure_message="A newer tenant source set claimed processing.",
        )
        run, created = CuratedProcessingRun.objects.get_or_create(
            organization_id=organization_id,
            processing_key=processing_key,
            defaults={
                "contract_version": CONTRACT_VERSION,
                "transform_version": TRANSFORM_VERSION,
                "source_publications": sources,
                "status": CuratedRunStatus.RUNNING,
                "attempt_token": token,
            },
        )
        run = CuratedProcessingRun.objects.select_for_update().get(pk=run.pk)
        if run.source_publications != sources:
            raise CuratedProcessingError(
                "Processing identity conflicts with stored source metadata."
            )
        if not created and run.status == CuratedRunStatus.COMPLETED:
            return run, None
        run.status = CuratedRunStatus.RUNNING
        run.attempt_token = token
        run.attempt_count = 1 if created else run.attempt_count + 1
        run.input_manifest_key = ""
        run.started_at = timezone.now()
        run.finished_at = None
        run.failure_class = ""
        run.failure_message = ""
        run.save(
            update_fields=(
                "status",
                "attempt_token",
                "attempt_count",
                "input_manifest_key",
                "started_at",
                "finished_at",
                "failure_class",
                "failure_message",
            )
        )
    return run, token


def _stage_input_manifest(*, run, token, sources):
    storage = _storage()
    manifest = {
        "contract_version": CONTRACT_VERSION,
        "transform_version": TRANSFORM_VERSION,
        "organization_id": str(run.organization_id),
        "processing_run_id": run.pk,
        "processing_key": run.processing_key,
        "attempt_token": str(token),
        "sources": sources,
    }
    raw = _canonical_json(manifest)
    if len(raw) > MAX_MANIFEST_BYTES:
        raise CuratedProcessingError("Bounded Spark source manifest exceeds its size limit.")
    key = f"{INPUT_PREFIX}/{run.organization_id}/{run.processing_key[:16]}/{token.hex}.json"
    stored_key = storage.save(key, ContentFile(raw, name=f"{token}.json"))
    try:
        path = _absolute_path(storage, stored_key)
        if not path.is_file() or path.stat().st_size != len(raw):
            raise CuratedProcessingError("Staged Spark input manifest failed size verification.")
        digest = hashlib.sha256(path.read_bytes()).digest()
        if digest != hashlib.sha256(raw).digest():
            raise CuratedProcessingError(
                "Staged Spark input manifest failed read-back verification."
            )
        with transaction.atomic():
            locked = CuratedProcessingRun.objects.select_for_update().get(pk=run.pk)
            if locked.attempt_token != token or locked.status != CuratedRunStatus.RUNNING:
                raise StaleCuratedAttempt("A newer attempt took ownership before Spark submission.")
            locked.input_manifest_key = stored_key
            locked.save(update_fields=("input_manifest_key",))
    except Exception:
        storage.delete(stored_key)
        raise
    organization_hex = uuid.UUID(str(run.organization_id)).hex
    stage_key = f"{STAGING_PREFIX}/o{organization_hex}/a{token.hex}"
    return {
        "organization_id": str(run.organization_id),
        "run_id": str(run.pk),
        "attempt_token": str(token),
        "input_manifest_path": str(_absolute_path(storage, stored_key)),
        "output_root": str(_absolute_path(storage, stage_key)),
        "spark_args": [
            "--input-manifest",
            str(_absolute_path(storage, stored_key)),
            "--output-root",
            str(_absolute_path(storage, stage_key)),
            "--organization-id",
            str(run.organization_id),
            "--run-id",
            str(run.pk),
            "--processing-key",
            run.processing_key,
            "--attempt-token",
            str(token),
        ],
    }


def prepare_curated_runs():
    """Claim deterministic tenant/input sets and stage small source manifests."""
    prepared = []
    for organization_id, publications in sorted(_latest_source_publications().items()):
        if not REQUIRED_SOURCE_DATASETS.issubset(publications):
            continue
        sources = [
            _source_descriptor(publication)
            for dataset in sorted(publications)
            for publication in publications[dataset]
        ]
        run, token = _claim_processing_run(organization_id=organization_id, sources=sources)
        if token is None:
            continue
        try:
            prepared.append(_stage_input_manifest(run=run, token=token, sources=sources))
        except Exception as exc:
            _mark_processing_failure(run.pk, token, exc)
            raise
    return prepared


def _mark_processing_failure(run_id, token, exc):
    with transaction.atomic():
        run = CuratedProcessingRun.objects.select_for_update().filter(pk=run_id).first()
        if run is None or run.attempt_token != token or run.status != CuratedRunStatus.RUNNING:
            return
        run.status = CuratedRunStatus.FAILED
        run.finished_at = timezone.now()
        run.failure_class = type(exc).__name__[:100]
        run.failure_message = "Spark processing failed; inspect sanitized Airflow task logs."
        run.save(update_fields=("status", "finished_at", "failure_class", "failure_message"))


def fail_curated_run(*, run_id, attempt_token, failure_class="SparkJobFailed"):
    """Record a terminal Airflow Spark task failure without exposing child output."""
    try:
        token = uuid.UUID(str(attempt_token))
    except ValueError as exc:
        raise CuratedProcessingError("Invalid processing attempt token.") from exc
    class_name = str(failure_class)[:100] or "SparkJobFailed"
    _mark_processing_failure(run_id, token, RuntimeError(class_name))


def _load_output_manifest(*, storage, run):
    if not run.input_manifest_key:
        raise CuratedProcessingError("Processing run has no verified input manifest.")
    organization_hex = uuid.UUID(str(run.organization_id)).hex
    root_key = f"{STAGING_PREFIX}/o{organization_hex}/a{run.attempt_token.hex}"
    root_path = _absolute_path(storage, root_key)
    manifest_path = root_path / "_assetflow_manifest.json"
    if not manifest_path.is_file() or manifest_path.stat().st_size > MAX_MANIFEST_BYTES:
        raise CuratedProcessingError("Spark output manifest is absent or exceeds its size limit.")
    raw = manifest_path.read_bytes()
    try:
        manifest = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CuratedProcessingError("Spark output manifest is malformed.") from exc
    expected_manifest_fields = {
        "contract_version",
        "transform_version",
        "organization_id",
        "processing_run_id",
        "processing_key",
        "attempt_token",
        "source_manifest_sha256",
        "datasets",
    }
    if set(manifest) != expected_manifest_fields:
        raise CuratedProcessingError("Spark output manifest fields do not match contract v1.")
    expected = {
        "contract_version": CONTRACT_VERSION,
        "transform_version": TRANSFORM_VERSION,
        "organization_id": str(run.organization_id),
        "processing_run_id": run.pk,
        "processing_key": run.processing_key,
        "attempt_token": str(run.attempt_token),
    }
    if any(manifest.get(key) != value for key, value in expected.items()):
        raise CuratedProcessingError(
            "Spark output manifest identity does not match its fenced run."
        )
    entries = manifest.get("datasets")
    if not isinstance(entries, list) or {row.get("name") for row in entries} != set(
        CURATED_SCHEMAS
    ):
        raise CuratedProcessingError(
            "Spark output manifest dataset set is incomplete or unexpected."
        )
    input_path = _absolute_path(storage, run.input_manifest_key)
    if input_path.stat().st_size > MAX_MANIFEST_BYTES:
        raise CuratedProcessingError("Spark input manifest exceeds its size limit.")
    input_bytes = input_path.read_bytes()
    if manifest.get("source_manifest_sha256") != hashlib.sha256(input_bytes).hexdigest():
        raise CuratedProcessingError("Spark output manifest source identity is invalid.")

    verified = []
    for entry in entries:
        if set(entry) != {"name", "organization_id", "row_count", "schema", "files"}:
            raise CuratedProcessingError("Curated dataset manifest fields are unexpected.")
        name = entry.get("name")
        if name not in CURATED_SCHEMAS or entry.get("schema") != [
            list(field) for field in CURATED_SCHEMAS[name]
        ]:
            raise CuratedProcessingError("Curated Parquet schema does not match contract v1.")
        if not isinstance(entry.get("row_count"), int) or entry["row_count"] < 0:
            raise CuratedProcessingError("Curated output row count is invalid.")
        if entry.get("organization_id") != str(run.organization_id):
            raise CuratedProcessingError("Curated output organization scope is invalid.")
        files = entry.get("files")
        if not isinstance(files, list) or not files:
            raise CuratedProcessingError("Curated Parquet output has no data files.")
        prefix = f"{name}/"
        verified_files = []
        actual_paths = {
            path.relative_to(root_path).as_posix() for path in (root_path / name).rglob("*.parquet")
        }
        for file_entry in files:
            if set(file_entry) != {"path", "byte_size", "sha256"}:
                raise CuratedProcessingError("Curated Parquet file manifest fields are unexpected.")
            relative = file_entry.get("path", "").replace("\\", "/")
            if not relative.startswith(prefix) or ".." in relative.split("/"):
                raise CuratedProcessingError("Curated output path is outside its tenant partition.")
            path = (root_path / relative).resolve()
            try:
                path.relative_to(root_path)
            except ValueError as exc:
                raise CuratedProcessingError(
                    "Curated output escaped the attempt directory."
                ) from exc
            if not path.is_file() or path.suffix != ".parquet":
                raise CuratedProcessingError("Curated output contains an invalid Parquet object.")
            if path.stat().st_size != file_entry.get("byte_size"):
                raise CuratedProcessingError("Curated Parquet object size did not verify.")
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            if digest.hexdigest() != file_entry.get("sha256"):
                raise CuratedProcessingError("Curated Parquet object digest did not verify.")
            verified_files.append(relative)
        if set(verified_files) != actual_paths:
            raise CuratedProcessingError(
                "Curated Parquet manifest does not enumerate every output file."
            )
        verified.append(
            {
                "name": name,
                "row_count": entry["row_count"],
                "schema": entry["schema"],
                "files": verified_files,
            }
        )
    manifest_key = f"{root_key}/_assetflow_manifest.json"
    return manifest_key, raw, verified


def publish_curated_run(*, run_id, attempt_token):
    """Verify staged Parquet outside locks, then publish one fenced DB pointer."""
    try:
        token = uuid.UUID(str(attempt_token))
    except ValueError as exc:
        raise CuratedProcessingError("Invalid processing attempt token.") from exc
    run = CuratedProcessingRun.objects.get(pk=run_id)
    if run.status == CuratedRunStatus.COMPLETED and run.attempt_token == token:
        return run.publication
    if run.attempt_token != token or run.status != CuratedRunStatus.RUNNING:
        raise StaleCuratedAttempt("A newer processing attempt owns this output.")
    storage = _storage()
    manifest_key, raw, datasets = _load_output_manifest(storage=storage, run=run)
    digest = hashlib.sha256(raw).hexdigest()
    manifest_size = len(raw)

    with transaction.atomic():
        locked = CuratedProcessingRun.objects.select_for_update().get(pk=run_id)
        if locked.status == CuratedRunStatus.COMPLETED and locked.attempt_token == token:
            return locked.publication
        if locked.attempt_token != token or locked.status != CuratedRunStatus.RUNNING:
            raise StaleCuratedAttempt("A newer processing attempt owns this publication.")
        publication = CuratedPublication.objects.create(
            run=locked,
            organization_id=locked.organization_id,
            manifest_key=manifest_key,
            manifest_sha256=digest,
            manifest_byte_size=manifest_size,
            datasets=datasets,
        )
        locked.status = CuratedRunStatus.COMPLETED
        locked.finished_at = timezone.now()
        locked.failure_class = ""
        locked.failure_message = ""
        locked.save(update_fields=("status", "finished_at", "failure_class", "failure_message"))
    return publication
