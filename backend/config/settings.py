"""Environment-driven Django settings for AssetFlow."""

import json
from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BASE_DIR.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
)
environ.Env.read_env(ROOT_DIR / ".env", overwrite=False)

SECRET_KEY = env("DJANGO_SECRET_KEY", default="")
DEBUG = env.bool("DEBUG", default=False)
ASSETFLOW_ENV = env("ASSETFLOW_ENV", default="development").strip().lower()
if not SECRET_KEY and not DEBUG:
    raise environ.ImproperlyConfigured("DJANGO_SECRET_KEY must be set when DEBUG is false.")
if not SECRET_KEY:
    SECRET_KEY = "assetflow-insecure-local-development-only"
if not DEBUG:
    if len(SECRET_KEY) < 50 or "replace-with" in SECRET_KEY.lower():
        raise environ.ImproperlyConfigured(
            "Production DJANGO_SECRET_KEY must be a unique random value of at least 50 characters."
        )

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
if not DEBUG and (not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS):
    raise environ.ImproperlyConfigured(
        "Production ALLOWED_HOSTS must list explicit public host names and cannot contain '*'."
    )
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "accounts.apps.AccountsConfig",
    "organizations.apps.OrganizationsConfig",
    "audit.apps.AuditConfig",
    "assets.apps.AssetsConfig",
    "depreciation.apps.DepreciationConfig",
    "transfers.apps.TransfersConfig",
    "maintenance.apps.MaintenanceConfig",
    "disposals.apps.DisposalsConfig",
    "verification.apps.VerificationConfig",
    "assurance.apps.AssuranceConfig",
    "reporting.apps.ReportingConfig",
    "analytics.apps.AnalyticsConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "common.request_id.RequestIdMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

database_url = env("DATABASE_URL", default="")
if not database_url:
    raise environ.ImproperlyConfigured(
        "DATABASE_URL is required. Use PostgreSQL for application and test environments."
    )
DATABASES = {"default": env.db("DATABASE_URL")}
if DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql":
    DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)
    pg_options = env("PGOPTIONS", default="")
    if pg_options:
        DATABASES["default"]["OPTIONS"] = {"options": pg_options}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = env("TIME_ZONE", default="Africa/Lagos")
USE_I18N = True
USE_TZ = True
CELERY_TIMEZONE = TIME_ZONE
STATIC_URL = env("STATIC_URL", default="/static/")
STATIC_ROOT = Path(env("STATIC_ROOT", default=str(BASE_DIR / "staticfiles")))
# Private application artifacts are never served through MEDIA_URL or Django URLs.
PRIVATE_MEDIA_ROOT = env("PRIVATE_MEDIA_ROOT", default=str(BASE_DIR / "private_media"))
ASSETFLOW_PRIVATE_STORAGE_BACKEND = env(
    "ASSETFLOW_PRIVATE_STORAGE_BACKEND", default="django.core.files.storage.FileSystemStorage"
)
ASSETFLOW_PRIVATE_STORAGE_OPTIONS = json.loads(
    env(
        "ASSETFLOW_PRIVATE_STORAGE_OPTIONS",
        default=json.dumps({"location": PRIVATE_MEDIA_ROOT}),
    )
)
if not isinstance(ASSETFLOW_PRIVATE_STORAGE_OPTIONS, dict):
    raise environ.ImproperlyConfigured("ASSETFLOW_PRIVATE_STORAGE_OPTIONS must be a JSON object.")
ANALYTICS_MEDIA_ROOT = env(
    "ANALYTICS_MEDIA_ROOT", default=str(ROOT_DIR / "backend" / "analytics_data")
)
ASSETFLOW_ANALYTICS_STORAGE_BACKEND = env(
    "ASSETFLOW_ANALYTICS_STORAGE_BACKEND", default="django.core.files.storage.FileSystemStorage"
)
ASSETFLOW_ANALYTICS_STORAGE_OPTIONS = json.loads(
    env(
        "ASSETFLOW_ANALYTICS_STORAGE_OPTIONS",
        default=json.dumps({"location": ANALYTICS_MEDIA_ROOT}),
    )
)
if not isinstance(ASSETFLOW_ANALYTICS_STORAGE_OPTIONS, dict):
    raise environ.ImproperlyConfigured("ASSETFLOW_ANALYTICS_STORAGE_OPTIONS must be a JSON object.")
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    "assetflow_private": {
        "BACKEND": ASSETFLOW_PRIVATE_STORAGE_BACKEND,
        "OPTIONS": ASSETFLOW_PRIVATE_STORAGE_OPTIONS,
    },
    "assetflow_analytics": {
        "BACKEND": ASSETFLOW_ANALYTICS_STORAGE_BACKEND,
        "OPTIONS": ASSETFLOW_ANALYTICS_STORAGE_OPTIONS,
    },
}
EVIDENCE_MAX_UPLOAD_BYTES = env.int("EVIDENCE_MAX_UPLOAD_BYTES", default=20 * 1024 * 1024)
REPORT_EXPORT_MAX_BYTES = env.int("REPORT_EXPORT_MAX_BYTES", default=100 * 1024 * 1024)
REPORT_EXPORT_RETENTION_DAYS = env.int("REPORT_EXPORT_RETENTION_DAYS", default=30)
ANALYTICS_MAX_RECORDS_PER_RUN = env.int("ANALYTICS_MAX_RECORDS_PER_RUN", default=100_000)
ANALYTICS_MAX_OUTPUT_BYTES = env.int("ANALYTICS_MAX_OUTPUT_BYTES", default=250 * 1024 * 1024)
ANALYTICS_LATE_ARRIVAL_OVERLAP_HOURS = env.int("ANALYTICS_LATE_ARRIVAL_OVERLAP_HOURS", default=48)
if (
    ANALYTICS_MAX_RECORDS_PER_RUN <= 0
    or ANALYTICS_MAX_OUTPUT_BYTES <= 0
    or ANALYTICS_LATE_ARRIVAL_OVERLAP_HOURS <= 0
):
    raise environ.ImproperlyConfigured("Analytics extraction limits and overlap must be positive.")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "common.pagination.StandardResultsPagination",
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "accounts.authentication.OrganizationJWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "EXCEPTION_HANDLER": "common.exceptions.api_exception_handler",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="redis://localhost:6379/1")
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60

EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default=(
        "django.core.mail.backends.smtp.EmailBackend"
        if env("EMAIL_HOST", default="")
        else "django.core.mail.backends.console.EmailBackend"
    ),
)
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=False)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="AssetFlow <no-reply@localhost>")
FRONTEND_BASE_URL = env("FRONTEND_BASE_URL", default="http://localhost:3000")
if ASSETFLOW_ENV == "production" and EMAIL_BACKEND in {
    "django.core.mail.backends.console.EmailBackend",
    "django.core.mail.backends.locmem.EmailBackend",
    "django.core.mail.backends.dummy.EmailBackend",
}:
    raise environ.ImproperlyConfigured(
        "Production must use a configured transactional email backend, not a development backend."
    )
if (
    ASSETFLOW_ENV == "production"
    and EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend"
    and not EMAIL_HOST
):
    raise environ.ImproperlyConfigured("EMAIL_HOST is required for production SMTP delivery.")

# Provisional work-unit size, not a demonstrated production population limit.
ASSURANCE_WORK_UNIT_SIZE = env.int("ASSURANCE_WORK_UNIT_SIZE", default=500)
ASSURANCE_MAX_TRANSIENT_RETRIES = env.int("ASSURANCE_MAX_TRANSIENT_RETRIES", default=5)
ASSURANCE_RETRY_SECONDS = env.int("ASSURANCE_RETRY_SECONDS", default=10)

SPECTACULAR_SETTINGS = {
    "TITLE": "AssetFlow API",
    "DESCRIPTION": "IAS 16-aligned fixed asset management API.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "ENUM_NAME_OVERRIDES": {
        "DepreciationMethodEnum": "assets.models.DepreciationMethod",
        "AssetStatusEnum": "assets.models.AssetStatus",
        "ObservedConditionEnum": "assets.models.AssetCondition",
        "AcquisitionStatusEnum": "assets.models.AcquisitionStatus",
        "AccountingPeriodStatusEnum": "depreciation.models.PeriodStatus",
        "DepreciationScheduleStatusEnum": "depreciation.models.ScheduleStatus",
        "TransferStatusEnum": "transfers.models.TransferStatus",
        "WorkOrderStatusEnum": "maintenance.models.WorkOrderStatus",
        "WorkOrderPriorityEnum": "maintenance.models.WorkOrderPriority",
        "DisposalStatusEnum": "disposals.models.DisposalStatus",
        "VerificationCampaignStatusEnum": "verification.models.CampaignStatus",
        "VerificationExceptionStatusEnum": "verification.models.ExceptionStatus",
        "AssuranceRunRunTypeEnum": "assurance.models.AssuranceRunType",
        "AssuranceRunStatusEnum": "assurance.models.AssuranceRunStatus",
        "AssuranceFindingFindingTypeEnum": "assurance.models.FindingType",
        "AssuranceFindingSourceEnum": "assurance.models.FindingSource",
    },
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"request_id": {"()": "common.request_id.RequestIdFilter"}},
    "formatters": {
        "standard": {
            "format": "{levelname} {asctime} request_id={request_id} {name}: {message}",
            "style": "{",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "filters": ["request_id"],
        }
    },
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO")},
}

if not DEBUG:
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
    SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=False)
    SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", default=False)
    X_FRAME_OPTIONS = "DENY"
