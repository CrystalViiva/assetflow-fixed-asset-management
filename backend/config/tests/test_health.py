import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_health_endpoint_reports_service_status(client):
    response = client.get(reverse("health-check"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "assetflow-api"}
