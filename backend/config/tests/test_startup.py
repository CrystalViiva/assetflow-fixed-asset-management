"""Validate fail-closed settings without connecting to a database or mail provider."""

import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "changes, expected",
    [
        ({}, None),
        ({"ASSETFLOW_ENV": "prodution"}, "ASSETFLOW_ENV"),
        ({"DEBUG": "true"}, "DEBUG"),
        ({"TRUSTED_PROXY_NETWORKS": "not-a-network"}, "CIDR"),
        ({"DJANGO_SECRET_KEY": ""}, "DJANGO_SECRET_KEY"),
        ({"BILLING_PROVIDER": "local_sandbox"}, "Payment collection is disabled"),
        ({"FRONTEND_BASE_URL": "http://app.example.test"}, "HTTPS"),
        ({"EMAIL_BACKEND": "django.core.mail.backends.console.EmailBackend"}, "EMAIL_BACKEND"),
        ({"EMAIL_BACKEND": "django.core.mail.backends.filebased.EmailBackend"}, "EMAIL_BACKEND"),
    ],
)
def test_production_startup_validation(changes, expected):
    environment = {
        **os.environ,
        "ASSETFLOW_ENV": "production",
        "DEBUG": "false",
        "DJANGO_SECRET_KEY": "synthetic-startup-test-secret-012345678901234567890123456789",
        "ALLOWED_HOSTS": "app.example.test",
        "DATABASE_URL": "postgresql://synthetic@127.0.0.1:1/not-connected",
        "FRONTEND_BASE_URL": "https://app.example.test",
        "EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend",
        "EMAIL_HOST": "smtp.example.test",
        "DEFAULT_FROM_EMAIL": "no-reply@example.test",
        "BILLING_PROVIDER": "disabled",
        "PAYSTACK_SECRET_KEY": "",
        "TRUSTED_PROXY_NETWORKS": "127.0.0.1/32",
        **changes,
    }
    result = subprocess.run(
        [sys.executable, "-c", "import config.settings"],
        env=environment,
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=15,
    )
    if expected:
        assert result.returncode != 0
        assert expected in result.stderr
    else:
        assert result.returncode == 0, result.stderr
