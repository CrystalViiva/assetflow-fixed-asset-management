# AssetFlow

AssetFlow is a fixed asset management system that implements selected asset-accounting concepts, including straight-line depreciation controls. It does not claim formal IFRS or IAS 16 compliance.

## Current state

- Milestones 1-9 and M10.1-M10.8 are implemented: backend foundation, asset/accounting workflows, deterministic assurance, Celery-backed assurance execution, daily assurance orchestration, scheduled monthly depreciation, organization-scoped reporting snapshots, scalable assurance execution, private verification evidence, durable CSV/JSON exports, Airflow-orchestrated analytics extraction, and PySpark curated analytics processing.
- The backend uses Django 5.2, Django REST Framework, PostgreSQL, psycopg3, JWT authentication, drf-spectacular/OpenAPI, and Celery/Redis workers with Beat orchestration.
- F1 connects the preserved React 19/TypeScript/Vite/Tailwind frontend to Django JWT authentication, Asset Register and Asset Detail Overview. Explicit mock mode remains available; other Django-mode screens show integration pending. See [the F1 frontend guide](docs/frontend-f1.md) for configuration, contracts, security tradeoffs and validation.
- PostgreSQL is required through `DATABASE_URL`; there is no implicit SQLite fallback.
- Reducing balance, units of production, sum-of-years-digits depreciation calculations, impairment, and AI/anomaly analytics are not implemented.

## Local development

Frontend: `npm ci` followed by `npm run dev`. Set `VITE_DATA_SOURCE=mock` for the local demo, or `django` with `VITE_BACKEND_API_URL=/api/v1` for authenticated real asset reads through the Vite development proxy. Validate with `npm test`, `npm run typecheck`, `npm run lint` and `npm run build`.

Backend: copy `.env.example` to `.env`, set a unique `DJANGO_SECRET_KEY` and local `POSTGRES_PASSWORD`, and make `DATABASE_URL` match your PostgreSQL credentials. Start PostgreSQL and Redis with `docker compose up -d db redis`. From `backend/`, install dependencies with `pip install -r requirements.txt`, then run `python manage.py migrate` and `python manage.py runserver`. The API health endpoint is `http://localhost:8000/api/v1/health/`; the OpenAPI UI is `http://localhost:8000/api/v1/docs/`.

To run the full stack, use `docker compose up --build`. Run backend checks from the repository root with `pytest -q`, `python backend/manage.py check`, `python backend/manage.py makemigrations --check --dry-run`, and `ruff check backend`.

For local analytics orchestration and Spark processing, use the optional development-only profiles: `docker compose --profile airflow --profile analytics up --build`. Airflow is separate from the default Django/Celery stack, extracts completed report snapshots to versioned JSONL, then submits tenant-scoped Spark processing. Its DAG starts paused. See [docs/analytics.md](docs/analytics.md) for the data contract, curated datasets, publication behavior, and development limits.

API and error-envelope details are in [docs/api.md](docs/api.md). Asset-domain decisions are in [docs/architecture.md](docs/architecture.md) and [docs/business-rules.md](docs/business-rules.md).
