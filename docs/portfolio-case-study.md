# AssetFlow: portfolio case study

## Problem

Organizations need more than an asset list. Finance needs a defensible cost basis, depreciation ledger, and disposal result. Operations needs custody, location, maintenance, and lifecycle history. Control teams need physical observations and reconciliation findings without accidentally changing the master record being reviewed.

## Goals

AssetFlow was designed to connect these concerns in one organization-scoped product while keeping their state models separate. The system makes accounting and control actions explicit, preserves history, and provides a separate batch analytics path without moving transactional authority out of PostgreSQL.

## Architecture

The web client is React and TypeScript. Django REST Framework provides the authenticated API and service-layer domain transitions. PostgreSQL stores authoritative state and protects invariants with transactions, locks, and constraints. Celery and Redis run operational background jobs. Report snapshots provide a durable boundary for exports and the Airflow/PySpark analytics pipeline.

## Hard engineering problems

- **Financial exactness:** derive capitalization from individual cost components and post a cent-precise SLM ledger sequentially.
- **Concurrency:** prevent duplicate capitalization and depreciation using locks, uniqueness constraints, and atomic updates.
- **Separate meanings:** keep person custody distinct from asset placement; keep physical observation distinct from corrected master state.
- **Deterministic assurance:** freeze input versions, persist work units, isolate candidates, and publish findings atomically.
- **Durable reporting:** capture ordered report rows and export those rows rather than rerunning mutable live queries.
- **Private files:** use server-generated storage identity, authenticated content endpoints, and size/SHA256 readback verification.
- **Multi-module frontend:** validate DTOs, scope cached queries to a session generation, avoid unsafe write retries, and reconcile ambiguous outcomes with Django.
- **Data engineering:** extract completed snapshots to versioned JSONL before typed Spark transforms publish tenant-scoped Parquet marts.

## Key tradeoffs

The project implements straight-line depreciation, not every accounting method. It records deterministic assurance findings rather than automated correction. Evidence is attached to verification, not a general asset document library. The live dashboard queries transactional aggregates; the batch data pipeline is not its serving layer. Operational correctness received more attention than production-scale benchmarking.

The F16 release gate found a frontend DTO check that rejected an assurance finding legitimately linked to both an asset and the verification observation that exposed it. A real cross-module smoke reproduced the issue; the DTO rule was corrected and regression-tested.

## Release evidence

F16 passed with zero remaining P0/P1 findings. The release snapshot had 231 frontend tests, 370 PostgreSQL-backed backend tests, passing mock/Django builds, and a real disposable golden lifecycle. The full evidence and limitations are in [F16 release gate](F16-full-system-release-gate.md).

## What I would build next

- Production operational work: hosted environment, backups/restore exercises, monitoring, alerting, and a load profile based on measured tenant usage.
- Accounting breadth: controlled estimate revisions, impairment accounting, component depreciation, and multi-currency only after requirements and ledger design are specified.
- Security operations: MFA/SSO, token/session policy improvements, and independent security assessment.
- Product breadth: generic asset documents or advanced analytics only when a real user workflow justifies them.

These are roadmap ideas, not current features.
