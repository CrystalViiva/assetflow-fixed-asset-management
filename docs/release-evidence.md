# F16 release evidence snapshot

These figures record the F16 release gate at commit `197ea6cb3bd26c03f1fbce612a81d4c29673de8d`; they are not a guarantee that later changes retain the same totals.

| Check | F16 result |
|---|---|
| Frontend tests | 231 passed across 21 files |
| Backend tests | 370 PostgreSQL-backed tests passed |
| TypeScript | Typecheck and lint passed |
| Frontend builds | Mock and Django production builds passed |
| Bundle | Authenticated App: 102.56 kB / 24.87 kB gzip; largest route about 80.65 kB |
| npm audit | 0 reported vulnerabilities |
| Django | System check and migration drift check passed |
| API contract | OpenAPI generation/validation passed |
| Python | Ruff and compilation passed |
| Integration | F1-F14 API milestone smokes and a unified disposable F16 golden lifecycle passed |

The golden lifecycle used the actual TypeScript repositories over HTTP against Django and a disposable PostgreSQL cluster. It reconciled acquisition/capitalization, SLM depreciation, transfer/custody, maintenance, verification, private evidence, assurance, snapshot/export, dashboard, audit, and disposal.

## Validation limits

- No browser-rendered screenshots were obtained; installed Chrome/Edge headless attempts did not produce usable rendered output.
- No live Airflow scheduler or Spark cluster was run. Airflow DAG/contract tests use stubs; PySpark was not installed and Java was unavailable.
- No production-scale load or database benchmark was run.
- No Python dependency vulnerability scanner was installed; npm audit passed, and Python source checks/full backend tests passed.
- F16 ran Celery tasks eagerly against isolated PostgreSQL; it did not operate a separate production-style Redis broker/worker deployment.

See the [full F16 report](F16-full-system-release-gate.md) for the accounting oracle, fixed DTO defect, findings, and security review.
