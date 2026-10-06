# Resume and portfolio bullets

These bullets describe implemented project work and F16 evidence. Do not present test totals or bundle measurements as business impact.

## Backend-focused

- Built a Django REST Framework/PostgreSQL fixed-asset domain with organization-scoped authorization, explicit service-layer workflows, audit events, and transactional accounting updates.
- Implemented Decimal-based acquisition capitalization, sequential SLM depreciation posting, and disposal gain/loss with PostgreSQL constraints and row locking.
- Designed resumable deterministic assurance runs with frozen versioned inputs, durable work units, candidate isolation, and atomic public finding publication.
- Added repeatable-read report snapshots, snapshot-derived asynchronous CSV/JSON exports, authenticated private downloads, and a versioned Airflow/PySpark analytics path.

## Full-stack-focused

- Integrated a React/TypeScript application with strict DTO boundaries, JWT session-generation query isolation, server-authoritative workflows, and safe reconciliation after ambiguous mutations.
- Delivered lifecycle screens for assets, accounting, custody/transfers, maintenance, verification/evidence, assurance, reports, organization administration, and audit.
- Reduced the authenticated App bundle from 605.50 kB to 102.56 kB (24.87 kB gzip) through route-level splitting; largest route measured about 80.65 kB.
- Validated the golden asset lifecycle through the real TypeScript client, HTTP, Django, and disposable PostgreSQL.

## Data-engineering-focused

- Built an Airflow-orchestrated extraction path from completed PostgreSQL report snapshots into versioned tenant-scoped JSONL, with overlap/checkpoint and attempt-publication controls.
- Implemented typed PySpark transformations that publish six curated Parquet marts while preserving Decimal precision and avoiding writes to transactional domain state.
- Added curated data for asset financial position, depreciation, maintenance, lifecycle events, assurance, and executive asset summary.

## Strong four-bullet version

- Developed AssetFlow, a Django/DRF, PostgreSQL, React/TypeScript fixed-asset management platform spanning capitalization, SLM depreciation, custody/transfers, maintenance, physical verification, assurance, disposal, reporting, and audit.
- Protected consequential accounting and workflow transitions with Decimal arithmetic, database transactions, row locks, uniqueness constraints, server-side tenant/RBAC enforcement, and backend-generated history.
- Built snapshot-based durable reporting and a separate Airflow/JSONL/PySpark/Parquet analytics pipeline; validated private evidence and export content with authenticated download and SHA256/size checks.
- Passed the F16 gate with 370 PostgreSQL-backed backend tests, 231 frontend tests, and a real disposable cross-domain lifecycle smoke; reduced the authenticated App bundle from 605.50 kB to 102.56 kB.

## Short two-bullet version

- Built a full-stack fixed-asset platform with transactional Django/PostgreSQL accounting and control workflows, a React/TypeScript client, private reporting/evidence, and deterministic assurance.
- Added a versioned Airflow/PySpark analytics pipeline and verified the end-to-end lifecycle with 370 backend tests, 231 frontend tests, and a disposable PostgreSQL integration smoke.

## Recommended GitHub repository description

Production-oriented Fixed Asset Management System built with Django REST Framework, PostgreSQL, React and Celery, featuring IAS 16-aligned depreciation workflows, lifecycle controls, verification, assurance, reporting and analytics.

Suggested topics: `django`, `django-rest-framework`, `postgresql`, `react`, `typescript`, `celery`, `redis`, `airflow`, `pyspark`, `fixed-assets`, `asset-management`, `accounting`, `data-engineering`.
