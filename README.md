# AssetFlow

AssetFlow is an IAS 16-aligned fixed asset management portfolio project. The existing React and TypeScript application remains backed by its mock repository while a Django REST API is built incrementally.

## Current state

- React 19, TypeScript, Vite, and Tailwind frontend with lifecycle screens and local mock data.
- Django 5.2 backend with PostgreSQL, DRF, OpenAPI, email-based users, organization structure, asset/category and acquisition APIs, transactional capitalization, auditable straight-line depreciation, explicit accounting periods, JWT authentication, and Celery/Redis configuration.
- PostgreSQL is required through `DATABASE_URL`; there is no implicit SQLite fallback.
- Reducing balance, units of production, and sum-of-years-digits calculation engines, transfers, maintenance, disposal, impairment, and reporting workflows remain future milestones.

## Local development

Frontend: `npm install` followed by `npm run dev`.

Backend: copy `.env.example` to `.env`, set a unique `DJANGO_SECRET_KEY` and local `POSTGRES_PASSWORD`, and make `DATABASE_URL` match your PostgreSQL credentials. Start PostgreSQL and Redis with `docker compose up -d db redis`. From `backend/`, install dependencies with `pip install -r requirements.txt`, then run `python manage.py migrate` and `python manage.py runserver`. The API health endpoint is `http://localhost:8000/api/v1/health/`; the OpenAPI UI is `http://localhost:8000/api/v1/docs/`.

To run the full stack, use `docker compose up --build`. Run backend checks from `backend/` with `python manage.py check`, `pytest`, `ruff check .`, and `ruff format --check .`.

API and error-envelope details are in [docs/api.md](docs/api.md). Asset-domain decisions are in [docs/architecture.md](docs/architecture.md) and [docs/business-rules.md](docs/business-rules.md).

## Engineering direction

The backend will use domain services for accounting workflows, PostgreSQL constraints and transactions for integrity, organization-scoped authorization, immutable audit records, and Decimal arithmetic for monetary values. See the project specification and upcoming `docs/` material for the domain rules and architecture decisions.
