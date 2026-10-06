# AssetFlow interview guide

Use these as study notes, not scripts. Explain the constraint or tradeoff behind each design, then use a concrete workflow from the repository.

## Product and architecture

### 1. What problem does AssetFlow solve?

It connects asset records, accounting balances, custody, placement, maintenance, physical verification, and approval history. The goal is a controlled asset lifecycle where financial and operational states can be reconciled without making every module mutate the same asset fields.

### 2. Walk me through the architecture.

The React/TypeScript UI calls a Django REST Framework API. Django services enforce domain transitions and organization/role scope. PostgreSQL stores the source of truth. Celery and Redis run application background work. Completed report snapshots feed a separate Airflow extraction and PySpark curation path.

### 3. Why Django and DRF?

Django supplies a mature ORM, migrations, transaction management, authentication integration, and constraints. DRF provides a consistent API boundary. The domain services keep consequential rules reusable outside serializer validation.

### 4. Why PostgreSQL?

The system needs transactions, row-level locking, uniqueness/check constraints, repeatable-read report capture, and durable job/publication metadata. Those guarantees are central to accounting and workflow integrity.

### 5. Why a service layer?

Serializer validation is not enough for operations involving several rows, concurrency, audit events, or a state transition. Services define the authoritative operation and its transaction boundary so alternate callers cannot bypass the rule.

### 6. How is tenant isolation enforced?

The authenticated Django user determines organization scope. API querysets, reference validation, serializers, services, and object lookups are organization-scoped; department-sensitive reads add the relevant department rule. Client-supplied organization IDs do not establish authority.

### 7. How does RBAC work?

The backend applies role-specific permissions per domain action, with department visibility where required. UI navigation hides unavailable actions for clarity, but direct API requests are still checked by Django.

## Accounting and state

### 8. How do you calculate depreciation?

Only SLM is implemented. The depreciable base is capitalized cost minus residual value. The nominal monthly amount is divided by useful life, rounded to cents with ROUND_HALF_UP. The schedule begins with the full calendar month containing the available-for-use date.

### 9. Why Decimal instead of float?

Binary floating-point cannot represent many decimal currency fractions exactly. Django calculates money with Decimal and returns money as strings; the frontend preserves those strings and formats them without computing accounting truth.

### 10. How do you prevent duplicate depreciation?

The posting service locks the period, asset, and schedule, checks that the requested period is the next expected period, and writes the ledger entry and balance update in one transaction. A database uniqueness constraint backs up the service rule for one asset/period.

### 11. How do transactions and locks help?

The lock serializes competing operations that would otherwise read the same prior state. The transaction ensures the ledger, asset snapshot, workflow status, and audit event commit together or roll back together. Constraints protect invariants even if another caller races.

### 12. Why separate custody from placement?

Custody answers who is responsible for an asset. Placement answers the department/location where it is recorded. A transfer changes placement only on completion; it does not automatically terminate the person's assignment.

### 13. How does transfer work?

A request captures source and destination placement. An authorized actor approves it; completion rechecks state and locks the asset/transfer before updating placement and writing history. Rejected, cancelled, or repeated terminal transitions follow their explicit workflow rules.

### 14. How does maintenance interact with accounting?

Maintenance costs and completion records are operational history. They do not automatically increase capitalized cost or modify useful life, residual value, depreciation method, posted depreciation, or book value.

### 15. How does disposal gain/loss work?

Completion snapshots cost and accumulated depreciation, derives carrying amount from those balances, and computes proceeds minus carrying amount. Approval and completion are controlled transitions; active custody, transfers, and work orders can block completion.

### 16. What is physical verification?

A campaign captures observations about registered assets or unregistered sightings. The system records mismatches and exceptions. Those observations are evidence for a person to review; they are not an implicit master-data correction.

### 17. Why doesn't verification update master data automatically?

An observation can be wrong, stale, or ambiguous. Automatically changing a tag, department, location, custodian, or accounting state would convert a control signal into an unreviewed write and erase the distinction between expected and observed data.

## Assurance and reporting

### 18. What does assurance do?

It deterministically compares authoritative domains and verification evidence under versioned rules and emits findings that users can review. It does not auto-correct assets and is not AI or anomaly prediction.

### 19. Why capture immutable assurance inputs?

The same run should evaluate a stable population even if live asset records change during execution. Frozen, versioned inputs make a run reproducible and allow durable work-unit recovery.

### 20. How does publication work?

Evaluation produces internal candidates. Public findings become visible only at the backend's successful publication boundary. Failed or partial runs do not present candidate rows as final findings.

### 21. How do live reports differ from snapshots?

A live report queries current data. A snapshot persists ordered report rows captured at a point in time. Its as-of value is capture time; it does not promise reconstruction of arbitrary previous state.

### 22. Why do exports use snapshots?

An export must reproduce the same rows and ordering after the live source changes. Rendering from a completed snapshot gives it a durable input. The backend publishes size/hash metadata and serves the private file through an authenticated endpoint.

### 23. How does the dashboard avoid double counting?

The backend aggregates asset financial measures at asset grain and aggregates one-to-many ledgers/workflows separately or with bounded subqueries/groupings. The browser renders authoritative values and does not download all assets to recompute totals.

### 24. How do private evidence downloads work?

The browser requests a UUID-based authenticated content endpoint. Django checks organization and domain authorization, then returns attachment bytes from private storage. Storage paths are not public URLs. The storage write is read back and checked against byte size and SHA256.

## Frontend and resilience

### 25. What happens after an ambiguous frontend mutation failure?

The client does not blindly replay unsafe writes. It refetches the authoritative resource/list using stable context. If the write committed, the current state is shown; otherwise the user can retry when the outcome is known. If uncertainty remains, it stays explicit.

### 26. How do you prevent user A's cache appearing for user B?

Query keys include authenticated identity and session generation. Logout invalidates effective visibility, stale requests are fenced, and a later login receives a different cache scope.

### 27. How is session refresh handled?

Access tokens live in memory; rotating refresh tokens are held in sessionStorage. Refresh is single-flight. Failed refresh clears the client session. A 403 remains an authorization result rather than being treated as logout.

### 28. What does Celery do?

Celery executes operational asynchronous Django work such as assurance run units, snapshot/export generation, and scheduled depreciation orchestration. Domain services still own the state changes.

## Data engineering

### 29. Why Airflow if Celery already exists?

Celery handles application background jobs close to Django workflows. Airflow orchestrates the scheduled, higher-level analytics extraction and retries from completed snapshots. It is not an alternative transaction engine.

### 30. What does PySpark do?

PySpark validates versioned JSONL envelopes and report schemas, preserves Decimal types, transforms records into curated outputs, and stages Parquet for a Django publication step. It does not query or mutate transactional domain tables directly.

### 31. What are the six marts?

asset_financial_position, depreciation_analytics, maintenance_analytics, asset_lifecycle_events, assurance_analytics, and executive_asset_summary.

### 32. How are late-arriving analytics records handled?

Extraction uses a configured overlap around the checkpoint and stable snapshot/row identities. The Spark consumer deduplicates by logical identity and fails conflicting duplicate payloads. Very old arrivals may require a full refresh. This is tested contract behavior; F16 did not run a production Airflow/Spark cluster.

## Difficult bug, tradeoffs, and learning

### 33. What was the hardest bug discovered?

The F16 cross-domain smoke produced a public assurance finding linked to both a registered asset and the physical observation that exposed it. The strict frontend DTO incorrectly treated those references as mutually exclusive, so valid findings failed contract parsing. The backend model allowed both when they matched. I changed the DTO boundary to reject only a finding with neither reference and added a regression test.

### 34. What would you improve next?

First validate a hosted operations setup: monitoring, backup/restore, credential rotation, real worker topology, and measured capacity. Product features such as impairment accounting or component depreciation need accounting requirements and ledger design before implementation.

### 35. Is AssetFlow fully IFRS compliant?

No. It implements IAS 16-aligned workflows with componentized capitalizable costs, SLM depreciation, accounting-period posting, carrying-value tracking, and disposal gain/loss. It lacks component depreciation, estimate revisions, impairment, decommissioning obligations, and multi-currency accounting.

### 36. What are the security limitations?

There is no MFA, SSO, immediate access-token revocation, malware scanning, CDR, cryptographic audit ledger, certification, or independent penetration-test claim. F16 validated source/test boundaries and disposable local flows, not a production security assessment.

### 37. How did you test it?

The F16 snapshot had 231 frontend tests, 370 PostgreSQL-backed backend tests, both frontend build modes, and a disposable TypeScript-to-HTTP-to-Django golden lifecycle. Tenant, RBAC, private-file, reporting, and workflow behavior also had domain-level regression coverage. The browser rendering attempt and live Airflow/Spark runtime were unavailable and are stated as limitations.

### 38. What did you learn?

The difficult part is preserving meaning between domains: a transfer is not a custody return, a verification exception is not an assurance finding, a live report is not a snapshot, and an accepted asynchronous request is not completed work. Strong contracts and server-side transactions make those boundaries visible and testable.

## Accounting deep dive

The golden fixture capitalized 1,001.00 and set residual to 100.00 over 36 months. Depreciable base is 901.00. Dividing by 36 gives 25.027777...; ROUND_HALF_UP produces 25.03 for the first posting. The remaining carrying amount is 975.97. Disposal proceeds of 1,200.00 less carrying amount of 975.97 produce a gain of 224.03.

The schedule caps each posting at the remaining depreciable base and the amount above residual. Because each nominal month is rounded to cents, the final schedule posting uses the remaining balance so cumulative depreciation does not exceed the depreciable base.

## Concurrency deep dive

Explain the specific service locks and the matching unique/check constraints rather than saying “the database handles concurrency.” Capitalization serializes on acquisition/asset. Depreciation locks period, asset, and schedule and also has a unique asset-period entry. Transfer and disposal serialize their status/asset changes. Snapshot and export requests use idempotency identities; export attempts use fencing so stale workers cannot publish over newer attempts.

A frontend retry is insufficient: two requests can race, arrive after a lost response, or come from a different client. Correctness must be enforced at the service/transaction/constraint boundary, with UI reconciliation only reducing accidental replay.

## Assurance deep dive

The execution boundary is capture immutable versioned inputs → persist durable work units → evaluate deterministic rules to internal candidates → atomically publish public findings. This adds database and coordination work for small runs, but gives the system a recoverable execution state and ensures incomplete evaluation does not leak partial findings as completed results.

F16 validated a disposable end-to-end run. It did not establish a production-scale assurance throughput claim.

## Data-engineering deep dive

PostgreSQL owns transactional truth. Celery runs application jobs. Airflow schedules snapshot extraction and retries. JSONL is the versioned handoff. PySpark validates/transforms it to curated Parquet. Django records a publication only after staged output verification. These tools have separate responsibilities rather than competing for domain authority.
