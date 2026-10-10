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
