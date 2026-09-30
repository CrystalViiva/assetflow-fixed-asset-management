# M10.7 analytics extraction and orchestration

## Authority and responsibilities

Django and PostgreSQL remain authoritative for every AssetFlow domain record,
report snapshot, evidence record, and export job. Celery continues to run
operational Django work such as assurance, depreciation posting, evidence cleanup,
report snapshot generation, and CSV/JSON exports. Airflow only schedules and
retries higher-level extraction of already-completed report snapshots. Its DAG
invokes `extract_analytics_snapshots`; all source selection, tenancy checks,
checkpoint transitions, and publication metadata remain in the Django analytics
service. DAG code contains no SQL or transactional model writes.

The Airflow task connects to the AssetFlow database because the Django command
reads snapshots and writes analytics-only checkpoint/run/publication tables. The
command filters every source query by one organization and writes only those
analytics tables. Airflow does not call domain mutation services or write domain
tables.

## Versioned contract and datasets

Contract version 1 is JSON Lines (`.jsonl`), selected because it is streaming,
partitionable by tenant and report type, readable without extra dependencies, and
straightforward to load in a later Spark job. A dedicated `assetflow_analytics`
storage alias stores outputs; local development uses the unserved
`backend/analytics_data/` directory. Deployments should configure a private,
shared object-storage backend for this alias. A run is bounded to 100,000 JSONL
records and 250 MiB by default; both limits are configurable. Exceeding either
limit fails the attempt without publishing or advancing its checkpoint.

Each mapped Airflow task handles one frozen M10.4 report type, and the Django
command processes every organization separately, including inactive organizations
with retained history. The contract currently covers
`asset_register`, `acquisitions`, `depreciation`, `accounting_periods`,
`assignments`, `transfers`, `work_orders`, `maintenance_costs`,
`maintenance_records`, `disposals`, `verification_campaigns`,
`verification_records`, `verification_exceptions`, `assurance_runs`,
`assurance_findings`, `assurance_occurrences`, and `lifecycle_history`.

Every JSONL record has the same explicit envelope:

| Field | Meaning |
| --- | --- |
| `contract_version` | Analytics envelope version (`1`) |
| `dataset` | Report type plus snapshot and contract version |
| `organization_id` | Owning organization UUID |
| `logical_record_id` | Stable snapshot UUID plus `snapshot` or row ordinal |
| `record_kind` | `snapshot` metadata or `row` payload |
| `source_snapshot_id` | Immutable M10.4 snapshot UUID |
| `source_snapshot_schema_version` | Frozen source report schema version |
| `source_row_id`, `source_ordinal` | Source row identity and deterministic ordering |
| `source_as_of` | Snapshot capture time, not arbitrary historical reconstruction |
| `source_generated_at` | Time the snapshot output completed |
| `extracted_at` | Time this analytics attempt started extraction |
| `payload` | Snapshot metadata or one report row |

Row payloads are checked against the frozen M10.4 schema registry. Unknown source
schema versions or unexpected fields fail closed. This also prevents storage keys
or other unapproved evidence metadata from entering the analytics dataset.

Asset register, acquisition, accounting-period, assignment, transfer, work-order,
disposal, campaign, exception, run, and finding rows describe the state captured
by each source snapshot. They are point-in-time observations, not a change log.
Depreciation entries, verification observations, assurance occurrences, and
lifecycle history are history-oriented report datasets, but each output still
records the snapshot that captured it. Repeated snapshots of the same domain row
are distinct observations because their source snapshot IDs differ. Report
snapshots created after a late business event use their own later `generated_at`;
the business event time remains inside its payload when available.

## Watermarks, retries, and publication

Checkpoint scope is `(organization_id, report_type)`. A source position is the
ordered tuple `(ReportSnapshot.generated_at, ReportSnapshot.id,
ReportSnapshotRow.ordinal)`. Snapshot metadata uses ordinal zero; source rows use
their frozen ordinal. The cursor includes the stable snapshot UUID and ordinal so
equal timestamps cannot skip later rows.

Each run looks back over the configured 48-hour completed-snapshot overlap. That
overlap catches delayed snapshot commits and same-timestamp UUIDs which sort below
the previous cursor. Replayed records retain the same `logical_record_id`; later
consumers must upsert on `(organization_id, dataset, logical_record_id)` instead
of appending blindly. For an unusually old delayed snapshot outside the overlap,
an operator can request a full refresh:

```powershell
cd backend
python manage.py extract_analytics_snapshots `
  --report-type asset_register `
  --run-key operator-replay-2026-09-30 `
  --full-refresh
```

The output process determines a bounded high watermark, claims a monotonically
increasing checkpoint generation and unique attempt token in a short transaction,
then streams and validates output outside any long database transaction. The
attempt writes an immutable token-specific object, verifies byte size and SHA-256
from storage read-back, then publishes its metadata and advances the watermark in
one short transaction. The committed publication row is the only consumer-visible
pointer to the object. A missing publication row means an object is incomplete or
orphaned and must not be loaded as a successful dataset.

Duplicate Airflow task delivery with the same logical run ID returns the existing
publication. A retry after failure reuses the run row with a new attempt token.
Concurrent attempts serialize their checkpoint claim; a newer token supersedes
the old worker. The old worker cannot publish or advance the cursor. If writing,
verification, or publication fails, the prior checkpoint stays intact and the
attempt object is deleted when possible. A process crash after object creation but
before publication can leave an unreferenced attempt object; it is never visible
as complete and can be removed by storage lifecycle policy.

## Numeric and temporal semantics

Financial values remain the exact decimal strings already captured in
`ReportSnapshotRow`; analytics does not parse them as binary floats. JSON output
is deterministic for a given record and ordered by snapshot time, snapshot UUID,
and row ordinal. Contract evolution requires a new envelope version and explicit
consumer migration; source snapshot schema versions remain separately identified.

`source_as_of` is the PostgreSQL capture time recorded by M10.4. It does not imply
that mutable state can be reconstructed for any date. `source_generated_at` is
snapshot completion/publication time. `extracted_at` is the analytics attempt
time. Domain event timestamps such as `posted_at`, `verified_at`, or `detected_at`
remain payload fields and are not substituted for the extraction watermark.

## Local development and deployment boundary

The optional Compose profile uses an isolated Airflow 3.3.2 development image,
its own PostgreSQL metadata database, and a shared local analytics-output volume.
It is a local development setup, not a production deployment. Django web startup
does not wait for Airflow. The web container remains the sole application
container that runs Django migrations; Airflow initializes only its separate
metadata database. The DAG is paused when created and runs daily at 03:00 in
`Africa/Lagos` after it is enabled in the Airflow UI.

Start the optional stack with:

```powershell
docker compose --profile airflow up --build
```

Airflow is available at `http://localhost:8080`; its development login password
is generated by the image and printed in the Airflow container logs. The default
backend stack remains `docker compose up --build` and does not start Airflow.
Airflow and AssetFlow use environment-provided credentials; no credential is
stored in the DAG or image source.

Airflow task retries are two attempts after the initial attempt. One DAG run
maps across the frozen report types, and each task processes organizations in
stable UUID order. Failures are retried by Airflow; a manual retry reuses the DAG
run ID. Celery recovery schedules remain responsible for operational jobs.

## Known limits and M10.8 handoff

This milestone extracts only snapshots that AssetFlow has already generated;
it does not trigger report snapshots or rebuild live domain rows. Output uses
local filesystem storage in development. Production shared storage permissions,
retention, and monitoring have not been validated. The overlap policy handles
ordinary delayed completion; very old late completions require a full refresh.
Analytics state and outputs have no public download API. No historical
reconstruction is claimed for mutable fields.

M10.8 can consume contract-v1 JSONL with an upsert key of organization, dataset,
and logical record ID. It may add a Spark reader and analytical transformations
in that later milestone; no Spark, anomaly detection, or AI functionality is
included here.
