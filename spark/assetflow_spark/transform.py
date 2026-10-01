"""Pure, tenant-scoped Spark ingestion, quality validation and curated marts."""

from analytics.curated_contracts import CURATED_SCHEMAS, MONEY_TYPE, QUANTITY_TYPE
from pyspark import StorageLevel
from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F
from pyspark.sql import types as T
from reporting.export_schemas import SCHEMA_V1

CONTRACT_VERSION = 1
SOURCE_SCHEMA_VERSION = 1
DATASET_SUFFIX = "_snapshots_v1"


def _spark_type(name):
    if name == "string":
        return T.StringType()
    if name == "integer":
        return T.IntegerType()
    if name == "long":
        return T.LongType()
    if name == "date":
        return T.DateType()
    if name == "timestamp":
        return T.TimestampType()
    if name.startswith("decimal("):
        precision, scale = (int(part) for part in name[8:-1].split(","))
        return T.DecimalType(precision, scale)
    raise ValueError(f"Unsupported curated Spark type: {name}")


def curated_schema(name):
    return T.StructType(
        [
            T.StructField(field, _spark_type(field_type), True)
            for field, field_type in CURATED_SCHEMAS[name]
        ]
    )


def schema_contract(frame):
    """Return field types using the stable curated contract names."""
    output = []
    for field in frame.schema.fields:
        dtype = field.dataType
        if isinstance(dtype, T.StringType):
            kind = "string"
        elif isinstance(dtype, T.IntegerType):
            kind = "integer"
        elif isinstance(dtype, T.LongType):
            kind = "long"
        elif isinstance(dtype, T.DateType):
            kind = "date"
        elif isinstance(dtype, T.TimestampType):
            kind = "timestamp"
        elif isinstance(dtype, T.DecimalType):
            kind = f"decimal({dtype.precision},{dtype.scale})"
        else:
            raise TypeError(f"Unsupported output data type {dtype.simpleString()}.")
        output.append((field.name, kind))
    return output


def _envelope_schema():
    payload = T.MapType(T.StringType(), T.StringType(), valueContainsNull=True)
    return T.StructType(
        [
            T.StructField("contract_version", T.IntegerType(), True),
            T.StructField("dataset", T.StringType(), True),
            T.StructField("organization_id", T.StringType(), True),
            T.StructField("logical_record_id", T.StringType(), True),
            T.StructField("record_kind", T.StringType(), True),
            T.StructField("source_snapshot_id", T.StringType(), True),
            T.StructField("source_snapshot_schema_version", T.IntegerType(), True),
            T.StructField("source_row_id", T.StringType(), True),
            T.StructField("source_ordinal", T.LongType(), True),
            T.StructField("source_as_of", T.StringType(), True),
            T.StructField("source_generated_at", T.StringType(), True),
            T.StructField("extracted_at", T.StringType(), True),
            T.StructField("payload", payload, True),
        ]
    )


def _fail_if_any(frame, condition, message):
    if frame.where(condition).limit(1).count():
        raise ValueError(message)


def _fail_if_duplicate(frame, keys, message):
    if frame.groupBy(*keys).count().where(F.col("count") > 1).limit(1).count():
        raise ValueError(message)


def _date_column(frame, name):
    raw = F.when(F.trim(F.col(name)) == "", F.lit(None)).otherwise(F.col(name))
    parsed = F.to_date(raw, "yyyy-MM-dd")
    _fail_if_any(frame, raw.isNotNull() & parsed.isNull(), f"Invalid date in {name}.")
    return parsed


def _timestamp_column(frame, name):
    raw = F.when(F.trim(F.col(name)) == "", F.lit(None)).otherwise(F.col(name))
    parsed = F.to_timestamp(raw)
    _fail_if_any(
        frame, raw.isNotNull() & parsed.isNull(), f"Invalid timestamp in {name}."
    )
    return parsed


def _decimal_column(frame, name, dtype):
    raw = F.when(F.trim(F.col(name)) == "", F.lit(None)).otherwise(F.col(name))
    parsed = F.expr(f"try_cast(`{name}` AS {dtype})")
    _fail_if_any(
        frame,
        raw.isNotNull() & parsed.isNull(),
        f"Invalid or overflowing decimal in {name}.",
    )
    return parsed


def _assert_tenant(frame, organization_id):
    _fail_if_any(
        frame,
        F.col("organization_id").isNull()
        | (F.col("organization_id") != organization_id),
        "A source or output record crossed its organization boundary.",
    )


def _parse_publication(spark, publications, organization_id):
    if isinstance(publications, dict):
        publications = [publications]
    if not publications:
        raise ValueError("At least one completed source publication is required.")
    report_type = publications[0]["dataset"]
    if report_type not in SCHEMA_V1:
        raise ValueError("Unsupported M10.7 source dataset.")
    if any(item["dataset"] != report_type for item in publications):
        raise ValueError("Source publication batch contains multiple datasets.")
    expected_dataset = f"{report_type}{DATASET_SUFFIX}"
    paths = [item["path"] for item in publications]
    if len(paths) != len(set(paths)):
        raise ValueError("Source publication batch repeats a storage path.")
    metadata_schema = T.StructType(
        [
            T.StructField("_source_path", T.StringType(), False),
            T.StructField("_expected_row_count", T.LongType(), False),
        ]
    )
    expected = spark.createDataFrame(
        [(item["path"], int(item["row_count"])) for item in publications],
        metadata_schema,
    )
    raw = spark.read.text(paths).withColumn("_source_path", F.input_file_name())
    actual_paths = raw.select("_source_path").distinct()
    if expected.join(actual_paths, "_source_path", "left_anti").limit(1).count():
        raise ValueError(
            "A source publication file is missing or contains no JSONL records."
        )
    if actual_paths.join(expected, "_source_path", "left_anti").limit(1).count():
        raise ValueError("Spark read an unregistered source publication file.")
    actual_counts = raw.groupBy("_source_path").count()
    if (
        expected.join(actual_counts, "_source_path", "left")
        .where(
            F.col("count").isNull() | (F.col("count") != F.col("_expected_row_count"))
        )
        .limit(1)
        .count()
    ):
        raise ValueError("M10.7 publication row count does not match its JSONL output.")
    raw_map = raw.select(
        F.from_json(
            F.col("value"),
            T.MapType(T.StringType(), T.StringType()),
            {"mode": "FAILFAST"},
        ).alias("record")
    )
    expected_envelope = F.array(
        *[
            F.lit(field)
            for field in sorted(
                (
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
            )
        ]
    )
    if (
        raw_map.where(F.array_sort(F.map_keys("record")) != expected_envelope)
        .limit(1)
        .count()
    ):
        raise ValueError("M10.7 envelope keys do not match contract v1.")
    parsed = (
        raw.select(
            F.from_json(F.col("value"), _envelope_schema(), {"mode": "FAILFAST"}).alias(
                "e"
            ),
            "_source_path",
        )
        .select("e.*", "_source_path")
        .persist(StorageLevel.DISK_ONLY)
    )
    if parsed.where(F.col("contract_version") != CONTRACT_VERSION).limit(1).count():
        raise ValueError("Unsupported M10.7 analytics contract version.")
    _fail_if_any(
        parsed,
        F.col("contract_version").isNull()
        | F.col("dataset").isNull()
        | (F.col("dataset") != expected_dataset)
        | (F.col("organization_id") != organization_id)
        | F.col("source_snapshot_schema_version").isNull()
        | (F.col("source_snapshot_schema_version") != SOURCE_SCHEMA_VERSION)
        | (F.col("record_kind").isNull())
        | (~F.col("record_kind").isin("snapshot", "row"))
        | F.col("source_snapshot_id").isNull()
        | F.col("logical_record_id").isNull()
        | F.col("source_as_of").isNull()
        | F.col("source_generated_at").isNull()
        | F.col("extracted_at").isNull()
        | F.col("payload").isNull(),
        "M10.7 envelope fields do not satisfy contract v1.",
    )
    expected_row_keys = sorted(field.name for field in SCHEMA_V1[report_type])
    row_keys = F.array_sort(F.map_keys("payload"))
    expected_keys = F.array(*[F.lit(key) for key in expected_row_keys])
    snapshot_keys = F.array_sort(F.map_keys("payload"))
    expected_snapshot_keys = F.array(
        F.lit("report_type"), F.lit("row_count"), F.lit("schema_version")
    )
    _fail_if_any(
        parsed,
        F.when(
            F.col("record_kind") == "row",
            (row_keys != expected_keys)
            | (F.col("source_ordinal") < 1)
            | F.col("source_row_id").isNull()
            | (F.trim(F.col("source_row_id")) == "")
            | (F.col("payload").getItem("id") != F.col("source_row_id")),
        ).otherwise(
            (snapshot_keys != expected_snapshot_keys)
            | (F.col("source_ordinal") != 0)
            | F.col("source_row_id").isNotNull()
            | (F.col("payload").getItem("report_type") != report_type)
            | (F.col("payload").getItem("schema_version") != str(SOURCE_SCHEMA_VERSION))
            | (
                F.col("logical_record_id")
                != F.concat(F.col("source_snapshot_id"), F.lit(":snapshot"))
            )
        ),
        "M10.7 payload does not match the frozen source schema.",
    )
    _fail_if_duplicate(
        parsed,
        ["_source_path", "logical_record_id"],
        "Duplicate M10.7 logical record IDs within a source publication.",
    )
    parsed = (
        parsed.withColumn("source_as_of", _timestamp_column(parsed, "source_as_of"))
        .withColumn(
            "source_generated_at", _timestamp_column(parsed, "source_generated_at")
        )
        .withColumn("extracted_at", _timestamp_column(parsed, "extracted_at"))
    )
    _fail_if_any(
        parsed,
        F.col("source_as_of").isNull()
        | F.col("source_generated_at").isNull()
        | F.col("extracted_at").isNull(),
        "Invalid required M10.7 timestamps.",
    )
    snapshots = parsed.where(F.col("record_kind") == "snapshot").select(
        "_source_path",
        "source_snapshot_id",
        "source_generated_at",
        "source_as_of",
        "payload",
    )
    rows = parsed.where(F.col("record_kind") == "row")
    if (
        rows.select("_source_path", "source_snapshot_id")
        .distinct()
        .join(
            snapshots.select("_source_path", "source_snapshot_id"),
            ["_source_path", "source_snapshot_id"],
            "left_anti",
        )
        .limit(1)
        .count()
    ):
        raise ValueError("M10.7 row refers to a snapshot without a metadata record.")
    row_counts = rows.groupBy("_source_path", "source_snapshot_id").agg(
        F.count(F.lit(1)).alias("actual_count")
    )
    metadata = (
        snapshots.select(
            "_source_path",
            "source_snapshot_id",
            F.col("payload").getItem("row_count").cast("long").alias("declared_count"),
        )
        .join(row_counts, ["_source_path", "source_snapshot_id"], "left")
        .fillna({"actual_count": 0})
    )
    _fail_if_any(
        metadata,
        F.col("declared_count").isNull()
        | (F.col("declared_count") != F.col("actual_count")),
        "M10.7 snapshot row count does not match its rows.",
    )
    _fail_if_any(
        rows,
        F.col("logical_record_id")
        != F.concat(
            F.col("source_snapshot_id"),
            F.lit(":row:"),
            F.col("source_ordinal").cast("string"),
        ),
        "M10.7 logical row identity does not match its stable snapshot/ordinal identity.",
    )
    typed_fields = []
    for field in SCHEMA_V1[report_type]:
        raw = F.element_at(F.col("payload"), F.lit(field.name))
        if field.kind == "integer":
            value = F.expr(f"try_cast(element_at(payload, '{field.name}') AS BIGINT)")
            _fail_if_any(
                rows,
                raw.isNotNull() & value.isNull(),
                f"Invalid integer in {report_type}.{field.name}.",
            )
        elif field.kind == "decimal":
            dtype = QUANTITY_TYPE if field.name == "quantity" else MONEY_TYPE
            value = F.expr(f"try_cast(element_at(payload, '{field.name}') AS {dtype})")
            _fail_if_any(
                rows,
                raw.isNotNull() & value.isNull(),
                f"Invalid or overflowing decimal in {report_type}.{field.name}.",
            )
        else:
            value = raw
        typed_fields.append(value.alias(field.name))
    selected = rows.withColumn("_typed_payload", F.struct(*typed_fields))
    columns = [
        F.lit(organization_id).alias("organization_id"),
        F.col("logical_record_id"),
        F.col("source_snapshot_id"),
        F.col("source_ordinal"),
        F.col("source_as_of"),
        F.col("source_generated_at"),
        F.col("extracted_at").alias("_extracted_at"),
        F.col("_typed_payload").getField("id").cast("string").alias("source_record_id"),
    ]
    columns.extend(
        F.col("_typed_payload").getField(field.name).alias(field.name)
        for field in SCHEMA_V1[report_type]
    )
    result = selected.select(*columns)
    _assert_tenant(result, organization_id)
    return result.persist(StorageLevel.DISK_ONLY)


def _empty_source_rows(spark, report_type):
    fields = [
        T.StructField("organization_id", T.StringType(), False),
        T.StructField("logical_record_id", T.StringType(), True),
        T.StructField("source_snapshot_id", T.StringType(), True),
        T.StructField("source_ordinal", T.LongType(), True),
        T.StructField("source_as_of", T.TimestampType(), True),
        T.StructField("source_generated_at", T.TimestampType(), True),
        T.StructField("_extracted_at", T.TimestampType(), True),
        T.StructField("source_record_id", T.StringType(), True),
    ]
    for field in SCHEMA_V1[report_type]:
        if field.kind == "integer":
            dtype = T.LongType()
        elif field.kind == "decimal":
            precision, scale = (18, 6) if field.name == "quantity" else (28, 2)
            dtype = T.DecimalType(precision, scale)
        else:
            dtype = T.StringType()
        fields.append(T.StructField(field.name, dtype, True))
    return spark.createDataFrame([], T.StructType(fields))


def _empty_curated(spark, dataset):
    return spark.createDataFrame([], curated_schema(dataset))


def _source_or_empty(spark, inputs, dataset, organization_id):
    publications = inputs.get(dataset)
    if not publications:
        return _empty_source_rows(spark, dataset)
    merged = _parse_publication(spark, publications, organization_id)
    stable_columns = [F.col(name) for name in merged.columns if name != "_extracted_at"]
    conflicting = (
        merged.groupBy("logical_record_id")
        .agg(
            F.countDistinct(F.to_json(F.struct(*stable_columns))).alias(
                "content_versions"
            )
        )
        .where(F.col("content_versions") > 1)
    )
    if conflicting.limit(1).count():
        raise ValueError(
            "Overlapping M10.7 publications disagree on a stable logical record."
        )
    window = Window.partitionBy("logical_record_id").orderBy(
        F.col("_extracted_at").desc(),
        F.col("source_generated_at").desc(),
        F.col("source_snapshot_id").desc(),
        F.col("source_ordinal").desc(),
    )
    return (
        merged.withColumn("_publication_rank", F.row_number().over(window))
        .where(F.col("_publication_rank") == 1)
        .drop("_publication_rank", "_extracted_at")
        .persist(StorageLevel.DISK_ONLY)
    )


def _current_records(frame, *, id_column="id"):
    _fail_if_any(frame, F.col(id_column).isNull(), "A source record has no stable ID.")
    window = Window.partitionBy("organization_id", F.col(id_column)).orderBy(
        F.col("source_generated_at").desc(),
        F.col("source_snapshot_id").desc(),
        F.col("source_ordinal").desc(),
    )
    return (
        frame.withColumn("_rn", F.row_number().over(window))
        .where(F.col("_rn") == 1)
        .drop("_rn")
    )


def _check_curated(frame, dataset, organization_id, keys):
    _assert_tenant(frame, organization_id)
    required = [
        name
        for name, _ in CURATED_SCHEMAS[dataset]
        if name in {"organization_id", *keys}
    ]
    for name in required:
        _fail_if_any(frame, F.col(name).isNull(), f"Required {dataset}.{name} is null.")
    _fail_if_duplicate(
        frame, ["organization_id", *keys], f"Duplicate logical keys in {dataset}."
    )
    schema = curated_schema(dataset)
    actual = [
        (field.name, field.dataType.simpleString()) for field in frame.schema.fields
    ]
    expected = [(field.name, field.dataType.simpleString()) for field in schema.fields]
    if actual != expected:
        raise ValueError(f"Curated {dataset} schema does not match contract v1.")
    return frame


def _empty_like_schema(spark, dataset):
    return _empty_curated(spark, dataset)


def build_curated_datasets(
    spark: SparkSession, inputs: dict, organization_id: str, manifest_sha256: str
):
    """Build six curated datasets from the latest complete v1 snapshot per source."""
    sources = {
        name: _source_or_empty(spark, inputs, name, organization_id)
        for name in SCHEMA_V1
    }
    for source in sources.values():
        _assert_tenant(source, organization_id)
    assets = _current_records(sources["asset_register"])
    acquisitions = _current_records(sources["acquisitions"])
    _fail_if_any(
        assets,
        F.col("asset_tag").isNull(),
        "Asset register contains a missing asset tag.",
    )
    _fail_if_duplicate(
        assets, ["organization_id", "asset_tag"], "Asset tags are not tenant-unique."
    )
    _fail_if_any(
        acquisitions,
        F.col("asset_tag").isNull(),
        "Acquisition contains a missing asset tag.",
    )
    _fail_if_duplicate(
        acquisitions,
        ["organization_id", "asset_tag"],
        "Acquisitions are not one-to-one by tenant asset tag.",
    )
    acquisition_fields = acquisitions.select(
        "organization_id",
        F.col("asset_tag").alias("_acq_asset_tag"),
        F.col("source_record_id").alias("acquisition_id"),
        F.to_date(F.nullif("acquisition_date", "")).alias("acquisition_date"),
        F.nullif("currency", "").alias("acquisition_currency"),
        F.col("total_cost").alias("acquisition_total_cost"),
    )
    _fail_if_duplicate(
        acquisition_fields,
        ["organization_id", "_acq_asset_tag"],
        "Acquisition join key is not unique.",
    )
    asset_financial = (
        assets.alias("a")
        .join(
            acquisition_fields.alias("q"),
            (F.col("a.organization_id") == F.col("q.organization_id"))
            & (F.col("a.asset_tag") == F.col("q._acq_asset_tag")),
            "left",
        )
        .select(
            F.col("a.organization_id"),
            F.col("a.source_record_id").alias("asset_id"),
            F.col("a.asset_tag"),
            F.col("a.name").alias("asset_name"),
            F.col("a.status"),
            F.col("a.condition"),
            F.col("a.category"),
            F.col("a.department"),
            F.col("a.department_id").cast("string").alias("department_id"),
            F.col("a.location"),
            F.col("a.purchase_cost").alias("capitalized_cost"),
            F.col("a.accumulated_depreciation"),
            F.col("a.current_book_value"),
            F.col("q.acquisition_id"),
            F.col("q.acquisition_date"),
            F.col("q.acquisition_currency"),
            F.col("q.acquisition_total_cost"),
            F.to_date(F.nullif(F.col("a.capitalization_date"), F.lit(""))).alias(
                "capitalization_date"
            ),
            F.to_date(F.nullif(F.col("a.available_for_use_date"), F.lit(""))).alias(
                "available_for_use_date"
            ),
            F.col("a.source_as_of"),
            F.col("a.source_generated_at"),
            F.col("a.source_snapshot_id"),
            F.col("a.logical_record_id").alias("source_logical_record_id"),
        )
    )
    asset_financial = _check_curated(
        asset_financial, "asset_financial_position", organization_id, ["asset_id"]
    )

    depreciation = _current_records(sources["depreciation"])
    depreciation = depreciation.select(
        F.lit(organization_id).alias("organization_id"),
        F.col("source_record_id").alias("depreciation_entry_id"),
        "asset_tag",
        "department",
        F.col("department_id").cast("string").alias("department_id"),
        F.col("year").cast("int").alias("accounting_year"),
        F.col("month").cast("int").alias("accounting_month"),
        F.make_date(
            F.col("year").cast("int"), F.col("month").cast("int"), F.lit(1)
        ).alias("period_start"),
        F.col("opening_book_value"),
        F.col("depreciation_amount").alias("depreciation_expense"),
        "accumulated_depreciation",
        F.col("closing_book_value"),
        _timestamp_column(depreciation, "posted_at").alias("posted_at"),
        "source_as_of",
        "source_snapshot_id",
        F.col("logical_record_id").alias("source_logical_record_id"),
    )
    _fail_if_any(
        depreciation,
        F.col("accounting_year").isNull()
        | F.col("accounting_month").isNull()
        | (F.col("accounting_month") < 1)
        | (F.col("accounting_month") > 12)
        | F.col("period_start").isNull(),
        "Depreciation accounting period is invalid.",
    )
    depreciation = _check_curated(
        depreciation,
        "depreciation_analytics",
        organization_id,
        ["depreciation_entry_id"],
    )

    work_orders = _current_records(sources["work_orders"])
    costs = _current_records(sources["maintenance_costs"])
    maintenance_records = _current_records(sources["maintenance_records"])
    maintenance = (
        work_orders.select(
            F.lit(organization_id).alias("organization_id"),
            F.lit("work_order").alias("record_kind"),
            F.col("source_record_id").alias("record_id"),
            "work_order_number",
            "asset_tag",
            "department",
            F.col("department_id").cast("string").alias("department_id"),
            "maintenance_type",
            "priority",
            "status",
            F.lit(None).cast("string").alias("cost_type"),
            F.coalesce(
                _timestamp_column(work_orders, "completed_at"),
                _timestamp_column(work_orders, "opened_at"),
            ).alias("event_at"),
            F.lit(None).cast(QUANTITY_TYPE).alias("quantity"),
            F.lit(None).cast(MONEY_TYPE).alias("unit_cost"),
            F.lit(None).cast(MONEY_TYPE).alias("total_cost"),
            "source_as_of",
            "source_snapshot_id",
            F.col("logical_record_id").alias("source_logical_record_id"),
        )
        .unionByName(
            costs.select(
                F.lit(organization_id).alias("organization_id"),
                F.lit("cost").alias("record_kind"),
                F.col("source_record_id").alias("record_id"),
                "work_order_number",
                "asset_tag",
                "department",
                F.col("department_id").cast("string").alias("department_id"),
                F.lit(None).cast("string").alias("maintenance_type"),
                F.lit(None).cast("string").alias("priority"),
                F.lit(None).cast("string").alias("status"),
                "cost_type",
                _timestamp_column(costs, "incurred_at").alias("event_at"),
                F.col("quantity"),
                F.col("unit_cost"),
                F.col("total_cost"),
                "source_as_of",
                "source_snapshot_id",
                F.col("logical_record_id").alias("source_logical_record_id"),
            )
        )
        .unionByName(
            maintenance_records.select(
                F.lit(organization_id).alias("organization_id"),
                F.lit("maintenance_record").alias("record_kind"),
                F.col("source_record_id").alias("record_id"),
                F.lit(None).cast("string").alias("work_order_number"),
                "asset_tag",
                "department",
                F.col("department_id").cast("string").alias("department_id"),
                "maintenance_type",
                F.lit(None).cast("string").alias("priority"),
                F.lit(None).cast("string").alias("status"),
                F.lit(None).cast("string").alias("cost_type"),
                _timestamp_column(maintenance_records, "maintenance_date")
                .cast("timestamp")
                .alias("event_at"),
                F.lit(None).cast(QUANTITY_TYPE).alias("quantity"),
                F.lit(None).cast(MONEY_TYPE).alias("unit_cost"),
                F.col("total_cost"),
                "source_as_of",
                "source_snapshot_id",
                F.col("logical_record_id").alias("source_logical_record_id"),
            )
        )
    )
    maintenance = _check_curated(
        maintenance,
        "maintenance_analytics",
        organization_id,
        ["record_kind", "record_id"],
    )

    event_sources = [
        (
            "acquisitions",
            "acquisition",
            "asset_tag",
            ("capitalization_date", "acquisition_date"),
            "status",
            "total_cost",
            "capitalized_cost",
        ),
        ("assignments", "assignment", "asset_tag", ("assigned_at",), "", "", ""),
        (
            "transfers",
            "transfer",
            "asset_tag",
            ("completed_at", "requested_at"),
            "status",
            "",
            "",
        ),
        (
            "work_orders",
            "work_order",
            "asset_tag",
            ("completed_at", "opened_at"),
            "status",
            "",
            "",
        ),
        (
            "maintenance_costs",
            "maintenance_cost",
            "asset_tag",
            ("incurred_at",),
            "",
            "total_cost",
            "maintenance_cost",
        ),
        (
            "maintenance_records",
            "maintenance_record",
            "asset_tag",
            ("maintenance_date",),
            "",
            "total_cost",
            "maintenance_cost",
        ),
        (
            "depreciation",
            "depreciation",
            "asset_tag",
            ("posted_at",),
            "",
            "depreciation_amount",
            "depreciation_expense",
        ),
        (
            "disposals",
            "disposal",
            "asset_tag",
            ("completed_at", "disposal_date"),
            "status",
            "proceeds",
            "disposal_proceeds",
        ),
        (
            "verification_records",
            "verification",
            "asset_tag",
            ("verified_at",),
            "result",
            "",
            "",
        ),
        (
            "verification_exceptions",
            "verification_exception",
            "asset_tag",
            ("created_at",),
            "status",
            "",
            "",
        ),
        (
            "assurance_occurrences",
            "assurance_occurrence",
            "asset_tag",
            ("detected_at",),
            "severity",
            "",
            "",
        ),
    ]
    lifecycle = None
    for (
        source_name,
        event_type,
        asset_key,
        time_keys,
        status_key,
        amount_key,
        amount_kind,
    ) in event_sources:
        source = _current_records(sources[source_name])
        amount = (
            _decimal_column(source, amount_key, MONEY_TYPE)
            if amount_key
            else F.lit(None).cast(MONEY_TYPE)
        )
        event_at = F.coalesce(
            *[_timestamp_column(source, field) for field in time_keys]
        )
        part = source.select(
            F.lit(organization_id).alias("organization_id"),
            F.concat(F.lit(source_name + ":"), F.col("source_record_id")).alias(
                "event_id"
            ),
            F.lit(source_name).alias("source_dataset"),
            F.col("source_record_id").alias("source_record_id"),
            F.lit(event_type).alias("event_type"),
            F.col(asset_key).alias("asset_tag"),
            event_at.alias("event_at"),
            F.col(status_key).alias("status")
            if status_key
            else F.lit(None).cast("string").alias("status"),
            F.lit(source_name).alias("source_entity_type"),
            F.col("source_record_id").alias("source_entity_id"),
            F.lit(amount_kind or None).cast("string").alias("amount_kind"),
            amount.alias("amount"),
            "source_as_of",
            "source_snapshot_id",
        )
        lifecycle = part if lifecycle is None else lifecycle.unionByName(part)
    audit_events = _current_records(sources["lifecycle_history"])
    audit_events = audit_events.where(
        F.col("entity_type").isin(
            "ASSET",
            "ACQUISITION",
            "ACCOUNTING_PERIOD",
            "DEPRECIATION_ENTRY",
            "ASSET_ASSIGNMENT",
            "ASSET_TRANSFER",
            "WORK_ORDER",
            "MAINTENANCE_RECORD",
            "MAINTENANCE_COST",
            "DISPOSAL",
            "PHYSICAL_VERIFICATION",
            "VERIFICATION_EXCEPTION",
            "ASSURANCE_RUN",
            "ASSURANCE_FINDING",
        )
    )
    lifecycle = lifecycle.unionByName(
        audit_events.select(
            F.lit(organization_id).alias("organization_id"),
            F.concat(F.lit("lifecycle_history:"), F.col("source_record_id")).alias(
                "event_id"
            ),
            F.lit("lifecycle_history").alias("source_dataset"),
            F.col("source_record_id").alias("source_record_id"),
            F.concat(F.lit("audit:"), F.col("action")).alias("event_type"),
            F.lit(None).cast("string").alias("asset_tag"),
            _timestamp_column(audit_events, "timestamp").alias("event_at"),
            F.lit(None).cast("string").alias("status"),
            F.col("entity_type").alias("source_entity_type"),
            F.col("entity_id").alias("source_entity_id"),
            F.lit(None).cast("string").alias("amount_kind"),
            F.lit(None).cast(MONEY_TYPE).alias("amount"),
            "source_as_of",
            "source_snapshot_id",
        )
    )
    lifecycle = _check_curated(
        lifecycle, "asset_lifecycle_events", organization_id, ["event_id"]
    )

    findings = _current_records(sources["assurance_findings"])
    occurrences = _current_records(sources["assurance_occurrences"])
    assurance = findings.select(
        F.lit(organization_id).alias("organization_id"),
        F.lit("finding").alias("record_kind"),
        F.col("source_record_id").alias("record_id"),
        F.col("source_record_id").alias("finding_id"),
        "asset_tag",
        "finding_type",
        "severity",
        "status",
        "source",
        F.col("occurrence_count").cast("long").alias("occurrence_count"),
        _timestamp_column(findings, "last_detected_at").alias("detected_at"),
        F.lit(None).cast("string").alias("description"),
        "source_as_of",
        "source_snapshot_id",
    ).unionByName(
        occurrences.select(
            F.lit(organization_id).alias("organization_id"),
            F.lit("occurrence").alias("record_kind"),
            F.col("source_record_id").alias("record_id"),
            F.col("finding_id").cast("string").alias("finding_id"),
            "asset_tag",
            "finding_type",
            "severity",
            F.lit(None).cast("string").alias("status"),
            F.lit(None).cast("string").alias("source"),
            F.lit(None).cast("long").alias("occurrence_count"),
            _timestamp_column(occurrences, "detected_at").alias("detected_at"),
            "description",
            "source_as_of",
            "source_snapshot_id",
        )
    )
    assurance = _check_curated(
        assurance, "assurance_analytics", organization_id, ["record_kind", "record_id"]
    )

    disposed = _current_records(sources["disposals"])
    disposal_completed = disposed.where(F.col("status") == "COMPLETED")
    metric_frames = [
        asset_financial.groupBy("organization_id").agg(
            F.count(F.lit(1)).cast("long").alias("asset_count"),
            F.sum(F.when(F.col("status") == "ACTIVE", 1).otherwise(0))
            .cast("long")
            .alias("active_asset_count"),
            F.sum(F.when(F.col("status") == "DISPOSED", 1).otherwise(0))
            .cast("long")
            .alias("disposed_asset_count"),
            F.sum("capitalized_cost").alias("capitalized_cost"),
            F.sum("accumulated_depreciation").alias("accumulated_depreciation"),
            F.sum("current_book_value").alias("current_book_value"),
            F.max("source_as_of").alias("asset_register_as_of"),
        ),
        depreciation.groupBy("organization_id").agg(
            F.sum("depreciation_expense").alias("depreciation_expense_total")
        ),
        maintenance.where(F.col("record_kind") == "cost")
        .groupBy("organization_id")
        .agg(F.sum("total_cost").alias("maintenance_cost_total")),
        disposal_completed.groupBy("organization_id").agg(
            F.countDistinct("asset_tag")
            .cast("long")
            .alias("disposed_asset_count_from_disposals"),
            F.sum("proceeds").alias("disposal_proceeds"),
            F.sum("gain_or_loss").alias("disposal_gain_or_loss"),
        ),
        findings.groupBy("organization_id").agg(
            F.sum(F.when(F.col("status") == "OPEN", 1).otherwise(0))
            .cast("long")
            .alias("open_assurance_findings"),
            F.sum(F.when(F.col("severity") == "CRITICAL", 1).otherwise(0))
            .cast("long")
            .alias("critical_assurance_findings"),
        ),
    ]
    summary = spark.createDataFrame([(organization_id,)], ["organization_id"])
    for metric in metric_frames:
        summary = summary.join(metric, "organization_id", "full_outer")
    summary = summary.where(F.col("organization_id") == organization_id)
    zero_money = F.lit("0.00").cast(MONEY_TYPE)
    for name in (
        "capitalized_cost",
        "accumulated_depreciation",
        "current_book_value",
        "depreciation_expense_total",
        "maintenance_cost_total",
        "disposal_proceeds",
        "disposal_gain_or_loss",
    ):
        summary = summary.withColumn(
            f"_{name}_cast", F.expr(f"try_cast(`{name}` AS {MONEY_TYPE})")
        )
        _fail_if_any(
            summary,
            F.col(name).isNotNull() & F.col(f"_{name}_cast").isNull(),
            f"Executive aggregate overflows DecimalType for {name}.",
        )
    summary = summary.select(
        F.col("organization_id"),
        "asset_register_as_of",
        F.coalesce("asset_count", F.lit(0)).cast("long").alias("asset_count"),
        F.coalesce("active_asset_count", F.lit(0))
        .cast("long")
        .alias("active_asset_count"),
        F.coalesce(
            "disposed_asset_count", "disposed_asset_count_from_disposals", F.lit(0)
        )
        .cast("long")
        .alias("disposed_asset_count"),
        F.coalesce("_capitalized_cost_cast", zero_money).alias("capitalized_cost"),
        F.coalesce("_accumulated_depreciation_cast", zero_money).alias(
            "accumulated_depreciation"
        ),
        F.coalesce("_current_book_value_cast", zero_money).alias("current_book_value"),
        F.coalesce("_depreciation_expense_total_cast", zero_money).alias(
            "depreciation_expense_total"
        ),
        F.coalesce("_maintenance_cost_total_cast", zero_money).alias(
            "maintenance_cost_total"
        ),
        F.coalesce("_disposal_proceeds_cast", zero_money).alias("disposal_proceeds"),
        F.coalesce("_disposal_gain_or_loss_cast", zero_money).alias(
            "disposal_gain_or_loss"
        ),
        F.coalesce("open_assurance_findings", F.lit(0))
        .cast("long")
        .alias("open_assurance_findings"),
        F.coalesce("critical_assurance_findings", F.lit(0))
        .cast("long")
        .alias("critical_assurance_findings"),
        F.lit(manifest_sha256).alias("source_manifest_sha256"),
    )
    summary = _check_curated(summary, "executive_asset_summary", organization_id, [])

    outputs = {
        "asset_financial_position": asset_financial,
        "depreciation_analytics": depreciation,
        "maintenance_analytics": maintenance,
        "asset_lifecycle_events": lifecycle,
        "assurance_analytics": assurance,
        "executive_asset_summary": summary,
    }
    return {
        name: _check_curated(df, name, organization_id, _dataset_keys(name))
        for name, df in outputs.items()
    }


def _dataset_keys(dataset):
    return {
        "asset_financial_position": ["asset_id"],
        "depreciation_analytics": ["depreciation_entry_id"],
        "maintenance_analytics": ["record_kind", "record_id"],
        "asset_lifecycle_events": ["event_id"],
        "assurance_analytics": ["record_kind", "record_id"],
        "executive_asset_summary": [],
    }[dataset]
