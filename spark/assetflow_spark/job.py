"""Spark-submit entry point; consumes M10.7 publications and writes staged Parquet."""

import argparse
import hashlib
import json
import os
import shutil
import uuid
from pathlib import Path

from analytics.curated_contracts import (
    CONTRACT_VERSION,
    CURATED_SCHEMAS,
    TRANSFORM_VERSION,
)
from pyspark.sql import SparkSession

from assetflow_spark.transform import (
    build_curated_datasets,
    curated_schema,
    schema_contract,
)


def _canonical_json(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _assert_local_path(path, *, root):
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(
            "Analytics path escaped the configured shared storage root."
        ) from exc
    return resolved


def _hash_file(path):
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


def _acquire_attempt_lock(output_root):
    """Serialize duplicate deliveries of the same fenced attempt on its shared filesystem."""
    lock_path = output_root.with_name(output_root.name + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(2):
        try:
            descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            try:
                pid = int(lock_path.read_text(encoding="ascii"))
                os.kill(pid, 0)
            except (OSError, ValueError):
                try:
                    lock_path.unlink()
                except FileNotFoundError:
                    pass
                continue
            raise RuntimeError(
                "Another Spark delivery is processing this fenced attempt."
            )
        with os.fdopen(descriptor, "w", encoding="ascii") as stream:
            stream.write(str(os.getpid()))
            stream.flush()
            os.fsync(stream.fileno())
        return lock_path
    raise RuntimeError("Could not acquire the Spark attempt lock.")


def _existing_output_is_complete(output_root, *, identity, source_manifest_sha):
    manifest_path = output_root / "_assetflow_manifest.json"
    if not manifest_path.is_file():
        return False
    if manifest_path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("Existing Spark output manifest exceeds its bounded size.")
    try:
        manifest = json.loads(manifest_path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(
            "Existing Spark output manifest is corrupt; refusing to overwrite it."
        ) from exc
    expected = {**identity, "source_manifest_sha256": source_manifest_sha}
    if any(manifest.get(key) != value for key, value in expected.items()):
        raise ValueError(
            "Existing Spark output belongs to a different processing identity."
        )
    entries = manifest.get("datasets")
    if not isinstance(entries, list) or {entry.get("name") for entry in entries} != set(
        CURATED_SCHEMAS
    ):
        raise ValueError(
            "Existing Spark output manifest has an incomplete dataset set."
        )
    for entry in entries:
        name = entry["name"]
        if (
            entry.get("organization_id") != identity["organization_id"]
            or entry.get("schema") != [list(field) for field in CURATED_SCHEMAS[name]]
            or not isinstance(entry.get("row_count"), int)
            or entry["row_count"] < 0
            or not isinstance(entry.get("files"), list)
            or not entry["files"]
        ):
            raise ValueError(
                "Existing Spark output manifest fails curated contract validation."
            )
        actual = {
            path.relative_to(output_root).as_posix()
            for path in (output_root / name).rglob("*.parquet")
        }
        listed = set()
        for file_entry in entry["files"]:
            relative = file_entry.get("path", "").replace("\\", "/")
            if not relative.startswith(name + "/") or ".." in relative.split("/"):
                raise ValueError(
                    "Existing Spark output manifest contains an unsafe file path."
                )
            path = _assert_local_path(output_root / relative, root=output_root)
            if not path.is_file():
                raise ValueError("Existing Spark output file is missing.")
            size, digest = _hash_file(path)
            if size != file_entry.get("byte_size") or digest != file_entry.get(
                "sha256"
            ):
                raise ValueError(
                    "Existing Spark output file failed integrity verification."
                )
            listed.add(relative)
        if listed != actual:
            raise ValueError(
                "Existing Spark output manifest does not enumerate its files exactly."
            )
    return True


def _load_inputs(manifest_path, organization_id):
    manifest_path = Path(manifest_path).resolve(strict=True)
    if manifest_path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("Spark input manifest exceeds its bounded size.")
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    expected_fields = {
        "contract_version",
        "transform_version",
        "organization_id",
        "processing_run_id",
        "processing_key",
        "attempt_token",
        "sources",
    }
    if set(manifest) != expected_fields:
        raise ValueError(
            "Spark input manifest fields do not match its versioned contract."
        )
    if (
        manifest["contract_version"] != CONTRACT_VERSION
        or manifest["transform_version"] != TRANSFORM_VERSION
        or manifest["organization_id"] != organization_id
    ):
        raise ValueError(
            "Unsupported contract, transform version or organization in input manifest."
        )
    try:
        uuid.UUID(manifest["organization_id"])
        uuid.UUID(manifest["attempt_token"])
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("Input manifest has an invalid generated identity.") from exc
    if len(manifest["processing_key"]) != 64 or any(
        char not in "0123456789abcdef" for char in manifest["processing_key"]
    ):
        raise ValueError("Input manifest has an invalid deterministic processing key.")
    if not isinstance(manifest["sources"], list) or not manifest["sources"]:
        raise ValueError("Spark input manifest contains no source publications.")
    storage_root = Path(
        os.environ.get("ANALYTICS_MEDIA_ROOT", "/srv/assetflow/analytics")
    ).resolve()
    inputs = {}
    for source in manifest["sources"]:
        required = {
            "organization_id",
            "dataset",
            "contract_version",
            "publication_id",
            "run_id",
            "storage_key",
            "sha256",
            "byte_size",
            "row_count",
            "source_watermark_at",
            "published_at",
        }
        if set(source) != required or source["organization_id"] != organization_id:
            raise ValueError(
                "Source publication metadata is malformed or crosses organizations."
            )
        if source["contract_version"] != CONTRACT_VERSION:
            raise ValueError("Unsupported M10.7 contract version.")
        if (
            not isinstance(source["publication_id"], str)
            or not source["publication_id"]
        ):
            raise ValueError(
                "Input manifest contains an invalid source publication identity."
            )
        if source["dataset"] not in {
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
        }:
            raise ValueError("Unexpected M10.7 report dataset.")
        key = source["storage_key"].replace("\\", "/")
        if key.startswith("/") or any(
            part in {"", ".", ".."} for part in key.split("/")
        ):
            raise ValueError("Invalid analytics storage key.")
        source_path = _assert_local_path(storage_root / key, root=storage_root)
        if (
            not source_path.is_file()
            or source_path.stat().st_size != source["byte_size"]
        ):
            raise ValueError("Published M10.7 source size does not match its metadata.")
        size, digest = _hash_file(source_path)
        if size != source["byte_size"] or digest != source["sha256"]:
            raise ValueError(
                "Published M10.7 source digest does not match its metadata."
            )
        inputs.setdefault(source["dataset"], []).append(
            {
                **source,
                "path": source_path.as_uri(),
            }
        )
    if "asset_register" not in inputs:
        raise ValueError("A completed asset-register source publication is required.")
    return (
        manifest,
        hashlib.sha256(manifest_bytes).hexdigest(),
        inputs,
        storage_root,
    )


def _run(args):
    organization_id = str(uuid.UUID(args.organization_id))
    run_id = int(args.run_id)
    token = str(uuid.UUID(args.attempt_token))
    input_path = Path(args.input_manifest).resolve(strict=True)
    output_root = Path(args.output_root).resolve()
    storage_root = Path(
        os.environ.get("ANALYTICS_MEDIA_ROOT", "/srv/assetflow/analytics")
    ).resolve()
    _assert_local_path(input_path, root=storage_root)
    expected_parent = Path("curated") / "stg" / f"o{uuid.UUID(organization_id).hex}"
    try:
        relative = output_root.relative_to(storage_root)
    except ValueError as exc:
        raise ValueError(
            "Spark output path escaped the analytics storage root."
        ) from exc
    if relative.parts[:3] != expected_parent.parts or len(relative.parts) != 4:
        raise ValueError(
            "Spark output path does not match the server-generated tenant attempt layout."
        )
    if relative.parts[3] != f"a{uuid.UUID(token).hex}":
        raise ValueError(
            "Spark output path does not match its processing key and attempt token."
        )
    try:
        uuid.UUID(organization_id)
        uuid.UUID(token)
    except ValueError as exc:
        raise ValueError("Invalid Spark processing identity.") from exc

    manifest, manifest_sha, inputs, _ = _load_inputs(input_path, organization_id)
    if (
        manifest["processing_run_id"] != run_id
        or manifest["attempt_token"] != token
        or manifest["processing_key"] != args.processing_key
    ):
        raise ValueError("Spark command identity does not match its input manifest.")
    identity = {
        "contract_version": CONTRACT_VERSION,
        "transform_version": TRANSFORM_VERSION,
        "organization_id": organization_id,
        "processing_run_id": run_id,
        "processing_key": args.processing_key,
        "attempt_token": token,
    }
    lock_path = _acquire_attempt_lock(output_root)
    try:
        if _existing_output_is_complete(
            output_root, identity=identity, source_manifest_sha=manifest_sha
        ):
            return
        if output_root.exists():
            shutil.rmtree(output_root)
        output_root.mkdir(parents=True, exist_ok=False)

        spark = (
            SparkSession.builder.appName(
                f"assetflow-curated-{organization_id[:8]}-{args.processing_key[:12]}"
            )
            .config("spark.sql.session.timeZone", "UTC")
            .config("spark.sql.ansi.enabled", "true")
            .config("spark.sql.shuffle.partitions", "8")
            .getOrCreate()
        )
        spark.sparkContext.setLogLevel("WARN")
        try:
            outputs = build_curated_datasets(
                spark, inputs, organization_id, manifest_sha
            )
            dataset_manifest = []
            for name in sorted(CURATED_SCHEMAS):
                frame = outputs[name]
                count = frame.count()
                path = output_root / name
                frame.coalesce(4).write.mode("error").parquet(path.as_uri())
                read_back = spark.read.schema(curated_schema(name)).parquet(
                    path.as_uri()
                )
                if read_back.count() != count:
                    raise ValueError(
                        f"Parquet row-count verification failed for {name}."
                    )
                actual_schema = schema_contract(read_back)
                expected_schema = list(CURATED_SCHEMAS[name])
                if actual_schema != expected_schema:
                    raise ValueError(f"Parquet schema verification failed for {name}.")
                files = []
                for parquet_file in sorted(path.rglob("*.parquet")):
                    relative_file = parquet_file.relative_to(output_root).as_posix()
                    size, digest = _hash_file(parquet_file)
                    files.append(
                        {"path": relative_file, "byte_size": size, "sha256": digest}
                    )
                if not files:
                    raise ValueError(
                        f"Spark did not write Parquet data files for {name}."
                    )
                dataset_manifest.append(
                    {
                        "name": name,
                        "organization_id": organization_id,
                        "row_count": count,
                        "schema": [list(field) for field in CURATED_SCHEMAS[name]],
                        "files": files,
                    }
                )
            output_manifest = {
                **identity,
                "source_manifest_sha256": manifest_sha,
                "datasets": dataset_manifest,
            }
            raw_output_manifest = _canonical_json(output_manifest)
            temp_path = output_root / "_assetflow_manifest.json.tmp"
            manifest_path = output_root / "_assetflow_manifest.json"
            temp_path.write_bytes(raw_output_manifest)
            os.replace(temp_path, manifest_path)
            if (
                hashlib.sha256(manifest_path.read_bytes()).digest()
                != hashlib.sha256(raw_output_manifest).digest()
            ):
                raise ValueError("Spark output manifest read-back verification failed.")
        finally:
            spark.stop()
    finally:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-manifest", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--organization-id", required=True)
    parser.add_argument("--run-id", required=True, type=int)
    parser.add_argument("--processing-key", required=True)
    parser.add_argument("--attempt-token", required=True)
    _run(parser.parse_args())


if __name__ == "__main__":
    main()
