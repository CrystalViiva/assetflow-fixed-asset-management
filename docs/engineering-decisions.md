# Engineering decisions

## Service layer owns domain transitions

Views and serializers define the HTTP boundary, but domain services own validations that span records, transaction boundaries, locks, and audit events. This keeps business invariants from depending on one API path or a React screen.

## PostgreSQL is the transactional authority

Asset balances, posted accounting entries, workflow state, audit history, report snapshots, and asynchronous job publication state live in PostgreSQL. Database uniqueness and check constraints reinforce application validation during duplicate requests and concurrent transactions.

## Exact money crosses the API as strings

Django computes financial values with Decimal. JSON money values remain decimal strings and are validated at the frontend DTO boundary. The browser formats values but does not use binary floating-point arithmetic to create accounting totals.

## Consequential writes lock and commit related state together

Capitalization locks acquisition and asset state. Depreciation locks period, asset, and schedule and commits ledger entry plus balance snapshots atomically. Transfer and disposal lock their workflow/asset records. Database constraints backstop uniqueness. Client retries cannot provide these guarantees, so unsafe frontend mutations are not automatically replayed.

## Custody and placement are separate

An assignment records who has custody and its return history. A transfer records department/location placement changes and affects placement only when completed. This avoids interpreting a transfer as an implicit custody return.

## Verification records observed state; it does not correct the asset

Physical observations and exceptions are control records. Reviewers decide how to resolve discrepancies through their domain workflows. The verification service does not silently overwrite tag, placement, custodian, lifecycle, or financial fields.

## Assurance captures inputs and publishes atomically

An assurance run freezes versioned input rows, creates durable work units, evaluates deterministic rules into internal candidates, and publishes public findings only once evaluation succeeds. This increases execution bookkeeping compared with a single in-memory loop, but supports recovery, reproducibility, and a clear boundary between unpublished candidates and public findings.

## Snapshots and exports have different responsibilities

A live report reads current authorized data. A snapshot durably captures ordered report rows and a schema version at capture time. It is not arbitrary historical reconstruction. CSV/JSON exports read only completed snapshots, so export content is stable even after source records change.

## Operational dashboard and batch analytics are separate

The operational dashboard is a live PostgreSQL aggregate for current scope and freshness. Airflow extracts completed snapshots and PySpark builds curated marts for batch analysis. The dashboard does not depend on delayed Parquet publication, and the batch pipeline does not mutate application records.

## Private content is served by authenticated application endpoints

Evidence and report exports use server-generated storage identity, private storage, and readback size/hash verification. The browser fetches content with its authenticated session and never receives a public storage link.

## Ambiguous frontend mutation outcomes are reconciled

For operations that must not be blindly replayed, the frontend refetches authoritative state after a timeout or lost response. A committed operation is recognized from Django state; an uncertain outcome remains explicit until rechecked.

## Session generations fence stale results

Frontend query keys include authenticated identity and session generation. This prevents old requests/cached responses from being applied after logout or user switch without globally clearing unrelated application state.

## Public routes and authenticated feature routes load separately

The public landing/login shell does not import or fetch the authenticated tenant dashboard merely to render. Authenticated routes are lazy-loaded so initial navigation can load the shell before a domain screen.

## Tradeoffs left explicit

AssetFlow favors a small set of transactional, deterministic workflows over broader accounting coverage, generic document management, public SaaS provisioning, or predictive features. F16 measured bundle reduction and workflow correctness; it did not establish production traffic capacity or large-population assurance performance.

See the [accounting guide](accounting.md), [security guide](security.md), and [release evidence](release-evidence.md).
