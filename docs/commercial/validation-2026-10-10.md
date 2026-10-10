# Executed commercial validation — 2026-10-10

## Scope and environment

Continuation started at `6e1e396`; validated implementation/configuration ends at `4ff1166`. Existing accounting architecture and exact Decimal calculations were retained. Local database work used an owned PostgreSQL 17.10 cluster on loopback port **55463**, under ignored `.codex-resume-pg`; no unidentified/persistent customer database was migrated. Subsequent Linux CI used ephemeral PostgreSQL services and randomly named Compose volumes. Smoke scripts create and clean their disposable databases and private/email directories.

The session-only `.codex-resume/run.py` wrapper executes its remaining arguments with an explicit disposable `DATABASE_URL`, generated Django secret, `ASSETFLOW_ENV=test`, local captured mail, sandbox billing, memory Celery transport and private temporary directories. It does not select application credentials from `.env`. Parallel focused tests used their own `af_resume_*` database names. The wrapper and synthetic artifacts are intentionally ignored, not deliverable configuration. For reproduction, supply equivalent isolated settings or use the committed CI and smoke scripts; never substitute a customer database.

Below, `PY` means the executed `venv/Scripts/python.exe`; `RUN` means `PY .codex-resume/run.py PY`. Paths are shown with portable separators. Commands ran from the repository root.

## Remote release gates

[Actions run 38031535116](https://github.com/CrystalViiva/assetflow-fixed-asset-management/actions/runs/38031535116), on `2ec6566`, passed the backend, frontend and commercial-browser jobs. Downloaded job logs establish **445 backend tests passed in 202.09s** (`pytest`, working directory `backend`) and **243 frontend tests passed in 17.32s**, 23 files (`npm test`). TypeScript checks, Django checks, migration drift, Ruff and both frontend production build modes passed. The commercial-browser job passed `python scripts/commercial-smoke.py --port 55462` and `python scripts/commercial-lifecycle-smoke.py --port 55462` against its disposable PostgreSQL service. These remote full-suite counts include the final cases absent from the earlier local full-suite collection.

[Actions run 38031908335](https://github.com/CrystalViiva/assetflow-fixed-asset-management/actions/runs/38031908335), on `4ff1166`, adds `python scripts/ops/production_compose_smoke.py --output .codex-compose-evidence`. Its **production-compose job passed in 132.82s**. The script built the real production images and ran release migrations/static collection, Gunicorn/nginx/PostgreSQL/Redis/Celery/Beat, strict deployment checks, API proxy/HSTS/CSP, real public lead persistence, nonroot backend execution, and shared private-file access from web and worker. A Beat-issued heartbeat traversed Redis and the worker before reaching PostgreSQL. Lead/private-file records survived service restarts. An intentionally invalid registered task produced a `TypeError` failure record and made `check_operations` exit nonzero; that expected failure is an asserted success condition, not a failed job. All owned containers/volumes/network were removed. [Retained evidence and image IDs](evidence/production-compose-2026-10-10.json) identify the exact build/run.

All four jobs in run 38031908335 completed successfully, including the repeated backend, frontend and commercial-browser gates. This production-container exercise simulates the trusted TLS ingress header on an isolated network. It does not issue a real TLS certificate, connect SMTP, deploy to a customer host, test off-host backup retention, scan images, or initiate payments. The final delivery documentation commit changes only evidence/docs and uses `[skip ci]` to avoid another expensive regression run; application code matches the passing implementation commit.

## Local tests and checks

| Executed command | Result |
|---|---|
| `RUN -m pytest -q --tb=short -o cache_dir=.codex-resume/pytest --basetemp=.codex-resume/full-tmp --junitxml=.codex-resume/full.xml` | **439 passed**, 1284.53s; zero failures/errors/skips. |
| `RUN -m pytest backend/accounts/tests/test_identity.py backend/commercial/test_commercial.py backend/operations/test_operations.py backend/depreciation/tests/test_automation.py -q -x --tb=short -o cache_dir=.codex-resume/pytest --basetemp=.codex-resume/targeted3-tmp --junitxml=.codex-resume/targeted3.xml` | **54 passed**, 181.69s, after correcting the Celery test application leak. |
| `RUN -m pytest backend/commercial backend/operations -q --tb=short -o cache_dir=.codex-resume/pytest-provider --basetemp=.codex-resume/provider-final-tmp --junitxml=.codex-resume/provider-final.xml` | **42 passed**, 76.63s, final provider/reversal/operations regression. |
| `RUN -m pytest backend/commercial/test_paystack.py::test_operator_can_retry_exhausted_subscription_event -q` | **1 passed**, 44.54s; isolated database/cache/temp arguments also supplied. |
| `npm.cmd test -- --pool=threads --maxWorkers=1` | **242 passed**, 23 files, 124.76s. |
| `npm.cmd test -- --pool=threads --maxWorkers=1 src/views/CommercialViews.test.tsx` | **7 passed**, 6.62s, including the new provider status/cancellation error case. |
| `npm.cmd run typecheck`; `npm.cmd run lint` | Passed. Both scripts run TypeScript checks. |
| `PY -m ruff check backend scripts/commercial-lifecycle-smoke.py`; `PY -m ruff format --check backend` | Passed; 270 backend files formatted. |
| `PY -m ruff check scripts/commercial-lifecycle-smoke.py scripts/commercial-smoke.py scripts/ops/recovery_drill.py scripts/vendor-fonts.py` | Passed. |
| `RUN backend/manage.py check`; `RUN backend/manage.py makemigrations --check --dry-run` | Zero issues; no migration drift. |
| `PY backend/manage.py check --deploy --fail-level WARNING` with generated production settings | Passed, zero issues/silenced checks. Explicit synthetic HSTS include-subdomains/preload flags were enabled; domain owners must choose these deliberately. |
| `docker compose --env-file .codex-resume/compose.env -f docker-compose.production.yml config -q` with generated environment | Passed; no containers started. |
| `RUN scripts/ops/recovery_drill.py --port 55463 --output .codex-resume-recovery` | **Passed**, actual encrypt/decrypt/restore, 63.90s; details below. |
| `RUN scripts/commercial-lifecycle-smoke.py --port 55463` | **Passed**, real Django/PostgreSQL/TypeScript repositories and all 20 integrated checkpoints. |
| `RUN scripts/commercial-smoke.py --port 55463 --nginx .codex-commercial-tools/nginx/nginx-1.30.5/nginx.exe`, with `E2E_BROWSER_EXECUTABLE` set to installed Chrome | **4 passed**, zero skipped/unexpected/flaky, runner 146.76s. Builds the frontend and serves it through nginx/API proxy. |
| `node node_modules/vite/bin/vite.js build` with `VITE_DATA_SOURCE=django`, `VITE_BACKEND_API_URL=/api/v1` (inside browser runner) | Passed, 2.07s. No Django-mode mock fallback. |
| `npm.cmd audit --omit=dev`; `git diff --check` | Zero production dependency vulnerabilities; whitespace check passed. |

The local full backend suite collected before the last refund/dispute/operator-retry additions. Five new cases appear in the final 42-case subsystem run and one in the separate operator test. Likewise, the local seven-case frontend run adds one case to the preceding full 242-case run. Overlapping local counts are not additive coverage claims. The later remote full-suite passes (445 backend, 243 frontend) establish the complete final application regression.

## Integrated workflow evidence

The commercial lifecycle runner bootstraps an unscoped superuser and enables the explicit operator capability using the real management command. It then provisions a company over HTTP, captures its activation email, activates/logs in its administrator, invites/activates an employee and completes password recovery. It persists both demo and sales leads and verifies a second self-service company by captured email.

The same managed tenant completes real asset acquisition/capitalization, straight-line depreciation, custody/transfer, maintenance, verification/private evidence, reporting/snapshot exports, audit and disposal. Measured values: cost **1001.00**, depreciation **25.03**, net book **975.97**, sale **1200.00**, disposal gain **224.03**. The saved report remains ACTIVE when the live asset becomes DISPOSED; dashboard book value becomes zero after disposal.

Cross-tenant access and checkout simulation are denied. A successful owning-tenant payment grants entitlements; cancellation preserves its paid period. Only that disposable tenant's period timestamp is advanced to exercise expiration: writes are denied while the asset, depreciation ledger and report snapshot remain readable. Tenant suspension invalidates access with an existing JWT. Separate PostgreSQL tests cover capacity/identity concurrency, role injection, forged/replayed/out-of-order events and immutable plan terms. Background financial operations recheck access before posting.

Browser evidence is retained locally under `.codex-browser-6ad78473`: the report records four expected passes, zero errors/skips/flakes. Billing/mobile marketing screenshots were visually inspected; CSP/nosniff assertions pass. This is built static frontend plus nginx and Django `runserver`, not Gunicorn or hosted TLS.

## Actual restore evidence

`.codex-resume-recovery/evidence.json` records **68 migrations**, **two active tenants**, **two managed subscriptions**, **four audit events**, denied cross-tenant user access, exact Decimal total `1234567890.13`, matching private SHA256 `d22324e0a1fb22dbb77b5a4650fd55ab0b645ad7f2ce3a09709ecd09595f9951`, and rejection of the wrong age identity. It restored both PostgreSQL and private storage into disposable targets in **63.90s**. The recorded HEAD was `9c2551d` while the provider migration was in the working tree; this accurately describes its source state. Both drill databases and temporary keys/plaintext were cleaned by the runner; the encrypted bundle remains ignored.

This is stronger than script syntax or archive-index validation. It does not establish off-host retention, production-size recovery, the Bash host backup workflow, or the owner's key-recovery process.

## Failures investigated and limitations

- An ordered backend run initially had 35 passes and one `NotRegistered` failure: a Celery worker test left its app as the process default. The fix restores both prior current/default apps in `finally`; no production assertion or security test was weakened. The targeted 54-case and full 439-case reruns pass.
- The default frontend fork-worker run reported 239 passes plus an unhandled worker-start timeout and was treated as failed. The complete thread-worker rerun passed 242 tests without unhandled errors. A new UI test initially used a generic error incorrectly; it now exercises the real API error envelope and passes.
- The first nginx attempt encountered local sandbox configuration access denial; rerunning with authorized local service access passed. The first dependency audit hit sandbox networking/cache restrictions; the completed audit reports zero production vulnerabilities.
- Strict production checks initially reported W005/W021 with domain-wide HSTS flags disabled. Explicit synthetic settings pass; Compose now forwards the configurable flags. The defaults remain opt-in for domain-wide coverage/preload. No unrelated security check is silenced.
- The local Windows Docker Linux engine pipe is absent. After safe push, the available Linux CI runner permitted actual production image/runtime and Redis/Celery validation, which passed as recorded above. Image vulnerability scans, hosted TLS, production SMTP delivery, off-host backup/alerts and remote rollback remain unverified.
- Paystack tests use official-shaped local contracts and independently verified simulated provider responses. **No actual merchant sandbox requests or live charges occurred.** Production rejects billing providers other than `disabled`. Actual merchant event shapes/timing still need acceptance.
- GitHub CLI reports no authenticated host, but the public Actions API exposed job results. Existing Git credentials subsequently allowed read-only download of logs/artifacts, with credentials held only in memory and not forwarded to artifact-storage redirects. The remote passing runs above are verified evidence. Delivery and remote HEAD are checked separately through Git.

## Next gate

Run the [operations release procedure](../operations/runbook.md) on owner-controlled Linux staging with synthetic data, including real Redis/Celery, HTTPS/ingress, mail, durable storage, off-host backup recovery, alerts and rollback. Complete merchant test acceptance separately before enabling automated paid SaaS. The [release decision](release-decision.md) remains conditional on those results.
