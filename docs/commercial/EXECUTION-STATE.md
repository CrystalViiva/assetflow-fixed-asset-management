# Commercial execution checkpoint

## Recovery — 2026-10-10

- Starting/current implementation commit: `6e1e39666e6a574a592d9ae8b310d9c81d8fe8f2` on `main`. Four local commits follow C1 `1eb4880`; fetched `origin/main` is still C1. Nothing reset or discarded.
- Recovered commits: `31b2452` identity, operators, verified registration, leads, subscription enforcement and sandbox billing; `3051de3` real Django commercial UI and browser journeys; `66c61e9` encrypted recovery/browser tooling and deployment hardening; `6e1e396` scheduled financial-posting entitlement rechecks.
- Interrupted work: eleven modified documentation files plus customer workflows, managed onboarding and SaaS documentation. No staged changes or unfinished application migration. Release decision was still the C1 report; no execution checkpoint existed.
- Saved validation: `.codex-commercial-final-tests.xml` records **425 passed**, zero failures/errors/skips, 762.383s (2026-10-09). Saved application restore evidence records two tenants, 67 migrations, exact Decimal total, matching private-file hash, rejected wrong key and cross-tenant denial. These are prior-run evidence, not fresh validation.
- Current work: validate recovered identity/commercial/worker code against a new disposable PostgreSQL cluster (`.codex-resume-pg`, loopback port 55463), finish documentation handoff, then complete Paystack test subscription/invoice mapping and integrated commercial-to-accounting validation.
- External gates: Docker engine/hosted deployment, DNS/TLS, transactional mail delivery, off-host backup retention/recovery, operational alert delivery, merchant sandbox credentials and owner-reviewed commercial/legal commitments. No public deployment or actual payment sandbox validation claimed. Production payment collection remains disabled.
- Next implementation task: provider-specific recurring subscription mapping. Existing Paystack transport only initializes/verifies individual test transactions; local simulator covers lifecycle transitions.

## Recovered gate validated

- Fresh isolated PostgreSQL run: identity, commercial, operations and depreciation automation **54 passed in 181.69s** (`.codex-resume/targeted3.xml`). The initial ordered run exposed a worker-test Celery application leak (`NotRegistered` in later depreciation tests); cleanup now restores the prior current/default application. Assertions and production financial logic are unchanged.
- Command: `venv/Scripts/python.exe .codex-resume/run.py venv/Scripts/python.exe -m pytest backend/accounts/tests/test_identity.py backend/commercial/test_commercial.py backend/operations/test_operations.py backend/depreciation/tests/test_automation.py -q -x --tb=short -o cache_dir=.codex-resume/pytest --basetemp=.codex-resume/targeted3-tmp --junitxml=.codex-resume/targeted3.xml`.
- Ruff check/format and `git diff --check` passed for the test fix. Recovered documentation handoff is complete; recurring test-provider implementation is in progress and not yet validated.

## Recurring provider slice validated

- Current committed handoff: `9c2551d`. New provider changes ready for commit: immutable monthly test-plan mapping, tenant-owned provider customer/subscription mapping, recurring invoice renewal/grace, confirmed cancellation, refund/dispute holds, failed-event operator retry, billing UI status and operational alert counts. Production still rejects payment collection.
- Final provider/operations regression: **42 passed in 76.63s**; added operator-retry command test **1 passed in 44.54s**. React commercial tests **7 passed**; full frontend regression **242 passed** with thread workers. Default fork-worker run had a startup timeout; thread-worker rerun passed. Typecheck/lint, Ruff (270 files), Django check and migration drift check passed.
- Fresh encrypted restore: **passed**, 68 migrations, two tenants, Decimal sum `1234567890.13`, hash match, wrong key denied, cross-tenant denied; 63.90s. Source included uncommitted provider migration while HEAD was `9c2551d`.
- New integrated commercial lifecycle smoke **passed all 20 checkpoints** on a generated disposable database: managed activation, invitations/recovery, core asset accounting/lifecycle/export/audit, second-tenant signup/isolation, sandbox billing, cancellation/expiry preservation and suspension. Exact values: `1001.00 - 25.03 = 975.97`; disposal gain `224.03`.
- Full backend regression and nginx/browser revalidation are running. Docker was checked outside the sandbox: Linux engine pipe is absent. First nginx attempt was denied access to its sandbox-created configuration; rerunning with authorized local service access.
- Next task: finish integrated gates, commit provider and lifecycle slices, update release decision, safely push and verify remote HEAD. Real merchant sandbox and hosted operational gates remain external.
