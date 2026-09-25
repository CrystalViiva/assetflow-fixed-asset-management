# AssetFlow

AssetFlow is an IAS 16-aligned fixed asset management portfolio project. The existing React and TypeScript application remains backed by its mock repository while a Django REST API is built incrementally.

## Current state

- React 19, TypeScript, Vite, and Tailwind frontend with lifecycle screens and local mock data.
- Django 5.2 backend foundation with environment-based settings, DRF, OpenAPI routes, and a health endpoint.
- Backend development uses SQLite when `DATABASE_URL` is unset; PostgreSQL is configured through `DATABASE_URL` for shared and production environments.
- Authentication defaults to JWT and session authentication. Domain models and API resources are being added in subsequent milestones.

## Local development

Frontend: `npm install` followed by `npm run dev`.

Backend: install `backend/requirements.txt`, set values from `.env.example`, then run `python backend/manage.py runserver` from the repository root. The health endpoint is `http://localhost:8000/api/v1/health/`; the OpenAPI UI is `http://localhost:8000/api/v1/docs/`.

Run backend checks from `backend/` with `python manage.py check` and `pytest`.

## Engineering direction

The backend will use domain services for accounting workflows, PostgreSQL constraints and transactions for integrity, organization-scoped authorization, immutable audit records, and Decimal arithmetic for monetary values. See the project specification and upcoming `docs/` material for the domain rules and architecture decisions.
