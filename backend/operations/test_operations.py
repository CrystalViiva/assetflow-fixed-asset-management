import json
import logging
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from common.logging import JsonFormatter
from operations.api import operational_health
from operations.models import TaskFailure, WorkerPulse
from operations.signals import record_failure
from operations.tasks import heartbeat


@pytest.mark.django_db
def test_worker_storage_health_and_failure_redaction(settings, tmp_path):
    settings.STORAGES = {
        **settings.STORAGES,
        "assetflow_private": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
            "OPTIONS": {"location": str(tmp_path)},
        },
    }
    assert not operational_health()["worker_recent"]
    heartbeat()
    values = operational_health()
    assert values["worker_recent"] and values["private_storage"]
    record_failure(task_id="synthetic-job", exception=ValueError("secret-password"))
    record_failure(task_id="synthetic-job", exception=ValueError("secret-password"))
    assert TaskFailure.objects.count() == 1
    assert TaskFailure.objects.get().error_type == "ValueError"
    WorkerPulse.objects.update(seen_at=timezone.now() - timedelta(minutes=5))
    assert not operational_health()["worker_recent"]
    user = User.objects.create_user("normal@example.test", None)
    client = APIClient()
    client.force_authenticate(user)
    assert client.get("/api/v1/platform/health/").status_code == 403


def test_log_redaction():
    record = logging.LogRecord(
        "test",
        logging.ERROR,
        "test",
        1,
        "failed postgres://user:secret@db/db token=secret",
        (),
        None,
    )
    output = JsonFormatter().format(record)
    assert "secret" not in output
    assert json.loads(output)["level"] == "ERROR"
    failure = ValueError("raw private provider response")
    record.exc_info = (ValueError, failure, None)
    record.msg = "Provider returned raw private provider response"
    output = JsonFormatter().format(record)
    assert "private provider" not in output
    assert json.loads(output)["error_type"] == "ValueError"


@pytest.mark.django_db(transaction=True)
def test_real_celery_worker_heartbeat_and_failed_task():
    """Exercise task delivery/signals through a worker; memory transport, not Redis."""
    from celery import Celery
    from celery.contrib.testing.worker import start_worker
    from celery.signals import task_postrun
    from django.db import connections

    app = Celery(
        "operations_probe",
        broker="memory://",
        backend="cache+memory://",
        set_as_current=False,
    )

    @app.task(name="operations.probe")
    def probe(fail=False):
        heartbeat.run()
        if fail:
            raise ValueError("synthetic-secret-not-for-logs")
        return "delivered"

    def close_worker_connection(sender=None, **kwargs):
        if getattr(sender, "name", None) == "operations.probe":
            connections.close_all()

    task_postrun.connect(close_worker_connection, weak=False)
    try:
        with start_worker(app, pool="solo", perform_ping_check=False, shutdown_timeout=10):
            assert probe.delay().get(timeout=10) == "delivered"
            assert WorkerPulse.objects.filter(name="default").exists()
            failure = probe.delay(True)
            assert isinstance(failure.get(timeout=10, propagate=False), ValueError)
        assert TaskFailure.objects.get(task_id=failure.id).error_type == "ValueError"
    finally:
        task_postrun.disconnect(close_worker_connection)
        app.close()
