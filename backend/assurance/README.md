# M10.5 scalable assurance

The domain service executes **capture → durable work units → atomic publication**.
Celery advances persisted work and supplies delivery/recovery only. PostgreSQL is
the authority for run ownership, inputs, progress, candidates and public history.

## Execution and consistency

Public statuses remain PENDING, RUNNING, COMPLETED, FAILED and CANCELLED. Internal
phases are LEGACY, CAPTURE, EVALUATE, PUBLISH and DONE. Read-only run API metadata
includes the phase, evaluator/input versions, capture/seal timestamps, population
count and completed/total units. Existing result counters are assigned at publication.

The creation/dispatch services retain the original organization, actor, run type,
campaign predicates, stale threshold and observation cutoff. PHYSICAL runs capture
the campaign's expected population; other run types capture organization assets.
A campaign attached to FULL/OPERATIONAL restricts observation context, not the
whole asset population. Department/accountant/API/admin permissions are unchanged.

Capture runs in its own PostgreSQL REPEATABLE READ transaction, setting isolation
before the first query. It locks the run, not the asset population. Source queries
read a common MVCC snapshot. Inputs are written in bounded groups, then sealed with
the work manifest in the same commit. Capture time is distinct from dispatch/start
time; this is not historical reconstruction. A crash before the seal rolls back
capture completely; a fresh capture uses the same frozen scope predicates. Once
sealed, all retries use exactly the stored population and values.

Inputs explicitly store only fields used by rules: scalar asset/accounting values,
relation identifiers and display labels, observation values and exception/evidence
flags, assignment label, compact workflow status counts, disposal basis and schedule
and ledger aggregates. Each payload records input schema version 1, and each run
records evaluator version 1. Workers refuse incompatible versions. Payloads and
candidate comparison snapshots have a 64 KiB serialized size guard; an oversized
subject fails explicitly and publishes no findings. Open-workflow comparison text
also has a conservative 64 KiB expansion guard. These are subject safety guards,
not organization population limits. Source notes and unrestricted model dumps are
not captured.

Latest observation selection orders by asset, descending verified_at, created_at,
and primary key. Observed tags use Python `strip().casefold()` exactly. All captured
campaign observations participate in duplicate detection, including unregistered
and currently out-of-population registered observations. Without a selected
campaign, the latest registered observation per asset participates, still grouped
by campaign. Each work unit queries the complete immutable tag context, so duplicates
across work-unit boundaries are detected. Financial runs omit observation context.

Each subject belongs to exactly one ordered unit and its complete rule set is
evaluated together. Advancement holds the run row lock for one unit transaction.
Candidates and unit completion commit together. Duplicate delivery can advance the
next unfinished unit but cannot evaluate an already completed unit again. Different
runs progress independently; there are no leases or distributed locks.

Publication verifies manifest coverage and completed-unit/candidate counts, then
streams candidates in identity/type order through the domain finding service.
Finding updates, occurrences, audits, counters and COMPLETED commit atomically.
A failure after completed units or during publication leaves no public findings or
occurrences from that run; internal inputs/candidates remain retained. Public
selectors, admin and reporting never expose staged candidates.

The active-finding partial unique index arbitrates concurrent inserts; services
reread the winning row after conflict rather than prevalidating that uniqueness.
If the winner closes during the reread, publication retries transactionally.
Occurrences remain unique per finding/run. Late publication adds its own occurrence
without moving latest detection/comparison values backwards; equal detection times
use run UUID ordering. Terminal findings remain immutable and recurrence after
closure creates a new finding. Absence in a later run does not auto-resolve findings.

## Delivery, retry and recovery

`execute_assurance_run(run_id)` advances one phase/unit and publishes a continuation
after commit. Celery results may therefore report RUNNING. `execute_run` remains a
synchronous domain driver, using separate transactions; it returns on terminal state
or a scheduled transient retry. Execution cannot join an outer transaction.

Transient connection/serialization/deadlock/lock-timeout/query-cancellation failures
use persisted retry counts and exponential backoff. Success resets consecutive retry
counts. Failure recording compares the durable revision so a stale worker cannot
fail work another worker has already advanced. If the database itself is unavailable,
the attempt may fail before recording retry metadata; the run remains recoverable
from its last committed phase. Deterministic failures and exhausted retries produce
terminal FAILED. FAILED/CANCELLED runs require a new run; cancellation is pending-only.

Beat redispatches up to 100 eligible RUNNING/version-1 runs every 60 seconds, using
`skip_locked` and oldest-updated ordering. This repairs lost initial or continuation
publication without an outbox. Redispatch is fair across scans. It skips future retry
times and legacy/incompatible running executions. Normal daily assurance and monthly
depreciation schedules remain in place. Run one Beat scheduler.

Backend settings:

| Setting | Default | Meaning |
|---|---:|---|
| ASSURANCE_WORK_UNIT_SIZE | 500 | Subjects per unit, accepted range 1–10000; provisional, not an optimized production value |
| ASSURANCE_MAX_TRANSIENT_RETRIES | 5 | Consecutive transient retries for a phase/unit before terminal failure |
| ASSURANCE_RETRY_SECONDS | 10 | Initial exponential-backoff interval |

## Migration and rollout

`0003_scalable_execution` adds run execution metadata, three internal tables and
their constraints/indexes. Existing rows retain executor version 0 and are marked
LEGACY; their statuses, actors, timestamps, findings and occurrences are preserved.
No historical input snapshots are invented. Legacy pending runs initialize version 1
at dispatch. Legacy RUNNING runs are never automatically reinterpreted.

Drain old workers before deployment. Inventory legacy RUNNING runs and explicitly
resolve them using the old deployment/domain workflow before enabling recovery on
the new release. There is no automatic conversion or blanket retry of those runs.
Do not run incompatible worker versions against sealed inputs. Reversing the schema
after new executions have begun would discard internal execution history; retain
the schema when rolling application code back and reconcile unfinished work first.

## Performance and limitations

`tests/test_scaling.py` compares the actual M10.4 source at
`f9a915c9198751ec4ddf0ea4440a9ec3a2c13918` with the new path on an isolated PostgreSQL
test database. In shallow checkouts without that Git object the old comparison is
omitted; all new-engine population checks still run. The baseline uses the historical
execution/context code against the same current test schema, not a separate old
application deployment. Measurements use Python
tracemalloc (allocation peaks, not total process RSS or database memory) and an SQL
execution wrapper. Setup queries and broker delivery are excluded.

The final full-suite local measurements used one matching observation per asset, no findings,
and 100-subject units:

| Assets | Old seconds / queries / Python MiB | Capture seconds / queries / MiB | Evaluation seconds / queries / largest unit MiB | Publish seconds / queries |
|---:|---|---|---|---|
| 100 | 0.366 / 45 / 0.772 | 0.414 / 24 / 1.049 | 0.103 / 9 / 0.916 | 0.040 / 10 |
| 500 | 0.990 / 45 / 3.634 | 2.035 / 56 / 1.069 | 0.666 / 45 / 0.899 | 0.044 / 10 |
| 1000 | 2.130 / 45 / 7.334 | 4.176 / 96 / 1.112 | 1.624 / 90 / 0.919 | 0.037 / 10 |

The old path issued an asset-population FOR UPDATE query; capture and publication
issued none. Real concurrent-update tests confirm asset updates can proceed during
capture and the capture retains a consistent view. Persistence/checkpointing costs
make these small runs slower; no speedup or maximum supported population is claimed.
The reference context builder's quadratic list membership was also replaced by set
membership, and capture uses grouped ledger totals/counts/latest timestamps.

A separate 25-asset/50-finding sample required 860 publication queries and about
1.89 seconds with tracemalloc enabled. Per-finding validation, writes and audits
remain a substantial cost. Publication holds affected finding locks until commit.

Capture and publication remain population-dependent transactions. Capture retains
an MVCC snapshot and durable inputs require storage; PostgreSQL may scan/sort source
history. Evaluation transactions and Python collections are bounded by the unit
size and subject payload guards. Fully bounded publication would require versioned
public finding visibility across all readers/review workflows and is not implemented.
Measure realistic dense findings and history distributions before selecting deployment
settings or making capacity commitments. No retention purge, export, binary evidence
pipeline or frontend work is included.

## Validation

Tests cover equivalence, Unicode/campaign duplicate groups across units, frozen
values and population, repeatable-read concurrency, same-run claims, different-run
insert races, duplicate tasks, real worker process termination in all phases,
transient retries, lost continuations, completion gates, publication rollback,
tenant boundaries, legacy migration, and increasing PostgreSQL populations.

Run focused tests with `python -m pytest assurance/tests --reuse-db -p no:cacheprovider`.
Run the complete backend suite with `python -m pytest . --reuse-db -p no:cacheprovider`
from the backend directory; explicit `.` includes reporting tests as well.
