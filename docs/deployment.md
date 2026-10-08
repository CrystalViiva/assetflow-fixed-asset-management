# Deployment and local operations

## Topology

The deployment-oriented Compose file is `docker-compose.production.yml`. It describes:

- PostgreSQL 17 and Redis, without host-published ports.
- Django/Gunicorn API, with a health check.
- Celery worker for asynchronous jobs and Celery Beat for configured schedules.
- A React static build served by Nginx, which proxies `/api/v1/` to Django.
- Separate named volumes for PostgreSQL data, private evidence/exports, analytics files, and Django static files.

The frontend binds to loopback by default. Place a TLS-terminating reverse proxy or managed platform router in front of it. Forward the original host and `X-Forwarded-Proto: https`; Django trusts that proxy header when DEBUG is false. The example does not provision a certificate, DNS, firewall, managed database, or hosted provider account.

## Production environment

Create an ignored deployment environment file from the safe example, then replace its local placeholders before running Compose:

```sh
cp .env.example .env.production
```

The production Compose file requires:

- `DJANGO_SECRET_KEY`: unique high-entropy Django signing key.
- `POSTGRES_PASSWORD`: unique URL-safe PostgreSQL password; the Compose file inserts it into DATABASE_URL.
- `ALLOWED_HOSTS`: comma-separated exact host names serving the application.
- `CSRF_TRUSTED_ORIGINS`: explicit HTTPS origins used by Django admin/session CSRF checks.
- `FRONTEND_BASE_URL`: public HTTPS URL used when generating customer links.
- Transactional email: backend, SMTP host, credentials, TLS mode, and sender identity.

Optional settings include `ASSETFLOW_HTTP_PORT`, `TIME_ZONE`, `DB_CONN_MAX_AGE`, `LOG_LEVEL`, Celery worker concurrency, evidence/export limits, and analytics bounds. Compose fixes DEBUG false and defaults HTTPS redirect on. Production rejects a short/example signing key and wildcard/empty hosts. Set `SECURE_SSL_REDIRECT=true`, and configure trusted origins with `https://` values. The sample email backend logs messages to the console and is not a production delivery service; explicitly configure and test a transactional provider before onboarding customers.

Generate secrets locally without committing them:

```sh
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

Put generated values in a deployment secret store or an ignored runtime env file. Use a URL-safe PostgreSQL password because the Compose DATABASE_URL is assembled from that value. Do not place secrets in frontend build arguments or VITE_* variables.

## Release and startup sequence

Build the image and run migrations plus static collection as a single release operation before starting or scaling web workers:

```sh
docker compose --env-file .env.production -f docker-compose.production.yml build
docker compose --env-file .env.production -f docker-compose.production.yml --profile release run --rm migrate
docker compose --env-file .env.production -f docker-compose.production.yml up -d
```

The `migrate` service is opt-in and runs once; web/worker/Beat startup does not run migrations concurrently. After the services are healthy, create the initial organization/admin using the same deployment Compose file:

```sh
docker compose --env-file .env.production -f docker-compose.production.yml exec web python manage.py shell
```

Follow the interactive bootstrap example below. Check service health and logs with:

```sh
docker compose --env-file .env.production -f docker-compose.production.yml ps
docker compose --env-file .env.production -f docker-compose.production.yml logs --tail=100 web worker beat
```

The API liveness endpoint is `/api/v1/health/`; readiness is `/api/v1/ready/` and checks PostgreSQL. Compose uses readiness for the web healthcheck and separately gates startup on DB/Redis health. Neither endpoint probes Celery queue progress or external object storage; add provider-specific monitoring. API responses include a generated request ID and application logs include it for support correlation. API documentation routes are `/api/v1/schema/`, `/api/v1/docs/`, and `/api/v1/redoc/`. Restrict documentation/admin routes at the edge if required by deployment policy.

## Private files and durability

The production Compose configuration mounts a private persistent volume into Django and Celery worker containers only. Nginx cannot address the private evidence/export volume. Use a durable, access-controlled volume with backups and capacity monitoring. The repository's storage abstraction is configurable through Django storage settings, but the Compose file does not add or claim a particular cloud object-storage adapter.

Analytics output is stored separately from private evidence and static files. Production Airflow/Spark must use compatible shared private analytics storage and publication metadata access; the local Compose analytics profile is a development/reference topology, not a pre-provisioned production data platform.

## Direct local Django development

For local, non-container Django work, install `backend/requirements.txt`, provide a PostgreSQL DATABASE_URL, Redis URLs, and a local secret, then run migrations and `python backend/manage.py runserver`. Use the Vite proxy for same-origin API paths. PostgreSQL is required; there is no SQLite fallback.

The mock frontend is the safe zero-credential product demo. There is no built-in demo tenant/admin seed command or public sign-up flow. Do not make public Django mode fall back to mock data.

### First organization bootstrap

The API intentionally does not provide public organization provisioning. For a new private installation, an operator with database-backed shell access must create the first organization and initial accounts once. Enter the following in the Django shell using interactive prompts rather than putting passwords in shell history. This bootstrap technique is for initial private installation only; it is not an auditable repeatable customer onboarding or invitation workflow:

```python
from getpass import getpass
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from organizations.models import Organization

User = get_user_model()
operator_email = input("Operator superuser email: ").strip()
operator_password = getpass("Operator superuser password: ")
validate_password(operator_password, user=User(email=operator_email))
admin_email = input("Tenant administrator email: ").strip()
admin_password = getpass("Tenant administrator password: ")
validate_password(admin_password, user=User(email=admin_email))
with transaction.atomic():
    organization = Organization.objects.create(
        name=input("Organization display name: ").strip(),
        code=input("Unique organization code: ").strip().upper(),
        currency="NGN",
        timezone="Africa/Lagos",
    )
    User.objects.create_superuser(
        email=operator_email,
        password=operator_password,
        organization=organization,
    )
    User.objects.create_user(
        email=admin_email,
        password=admin_password,
        organization=organization,
        role="ADMIN",
    )
```

This is an operator-only bootstrap procedure, not a self-service onboarding flow. Store credentials in the deployment's secret-management process. Use the tenant administrator for normal organization administration; reserve the superuser for platform operations. Provisioning of later users is available through the authenticated organization administration UI.

## Deployment limitations

This is deployment-oriented configuration, not evidence of a hosted deployment or operational SLA. Configure TLS, DNS, backups, alerting, log retention, credential rotation, private-storage recovery, and capacity for the selected hosting environment. One Beat instance is expected for schedule ownership. No cloud provider or public deployment URL is configured in the repository.
