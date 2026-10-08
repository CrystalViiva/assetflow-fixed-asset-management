import json
from unittest.mock import Mock

import pytest
from django.test import RequestFactory
from django.urls import reverse

import config.views


@pytest.mark.django_db
def test_health_endpoint_reports_service_status(client):
    response = client.get(reverse("health-check"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "assetflow-api"}


@pytest.mark.django_db
def test_readiness_endpoint_checks_database(client):
    response = client.get(reverse("readiness-check"))

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "service": "assetflow-api"}


def test_readiness_view_returns_503_when_database_is_unavailable(monkeypatch):
    database = Mock()
    database.ensure_connection.side_effect = OSError("unavailable")
    monkeypatch.setattr(config.views, "connections", {"default": database})

    response = config.views.readiness_check(RequestFactory().get("/api/v1/ready/"))

    assert response.status_code == 503
    assert json.loads(response.content) == {"status": "not_ready", "service": "assetflow-api"}
