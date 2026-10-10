"""Run the 20-point commercial/financial journey on an owned disposable database."""

import argparse
import os
import runpy
import secrets
import sys
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--port", required=True, type=int)
args = parser.parse_args()
if args.port == 5432:
    parser.error("Use a dedicated disposable PostgreSQL cluster, not the default port.")
os.environ.update(
    DATABASE_URL=f"postgresql://assetflow@127.0.0.1:{args.port}/postgres",
    DJANGO_SECRET_KEY=secrets.token_urlsafe(64),
    DJANGO_SETTINGS_MODULE="config.settings",
    ASSETFLOW_ENV="test",
    DEBUG="false",
    SECURE_SSL_REDIRECT="false",
    BILLING_PROVIDER="local_sandbox",
    SELF_SERVICE_ENABLED="true",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    CELERY_BROKER_URL="memory://",
    CELERY_RESULT_BACKEND="cache+memory://",
    F16_COMMERCIAL_MODE="1",
)
sys.argv = ["f1-smoke.py", "--f16"]
runpy.run_path(str(Path(__file__).with_name("f1-smoke.py")), run_name="__main__")
