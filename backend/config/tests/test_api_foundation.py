import pytest
import yaml
from django.urls import reverse
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.test import APIClient, APIRequestFactory

from accounts.models import User
from common.exceptions import api_exception_handler
from common.pagination import StandardResultsPagination


@pytest.mark.django_db
def test_health_endpoint_is_lightweight_and_public(client):
    response = client.get(reverse("health-check"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "assetflow-api"}


@pytest.mark.django_db
def test_valid_login_returns_jwt_pair():
    User.objects.create_user("login@example.com", "strong-password")
    client = APIClient()

    response = client.post(
        reverse("token-obtain-pair"),
        {"email": "login@example.com", "password": "strong-password"},
        format="json",
    )

    assert response.status_code == 200
    assert "access" in response.data
    assert "refresh" in response.data


@pytest.mark.django_db
def test_invalid_login_returns_standard_authentication_error():
    User.objects.create_user("login@example.com", "strong-password")
    response = APIClient().post(
        reverse("token-obtain-pair"),
        {"email": "login@example.com", "password": "wrong-password"},
        format="json",
    )

    assert response.status_code == 401
    assert response.data["success"] is False
    assert response.data["error"]["code"] == "AUTHENTICATION_ERROR"


@pytest.mark.django_db
def test_refresh_endpoint_returns_rotated_token_pair():
    user = User.objects.create_user("login@example.com", "strong-password")
    token_response = APIClient().post(
        reverse("token-obtain-pair"),
        {"email": user.email, "password": "strong-password"},
        format="json",
    )

    response = APIClient().post(
        reverse("token-refresh"), {"refresh": token_response.data["refresh"]}, format="json"
    )

    assert response.status_code == 200
    assert "access" in response.data
    assert "refresh" in response.data

    reuse_response = APIClient().post(
        reverse("token-refresh"), {"refresh": token_response.data["refresh"]}, format="json"
    )
    assert reuse_response.status_code == 401
    assert reuse_response.data["error"]["code"] == "AUTHENTICATION_ERROR"


@pytest.mark.django_db
def test_protected_endpoint_rejects_anonymous_and_accepts_jwt():
    user = User.objects.create_user("login@example.com", "strong-password")
    url = reverse("authenticated-user")
    client = APIClient()

    anonymous_response = client.get(url)
    assert anonymous_response.status_code == 401
    assert anonymous_response.data["error"]["code"] == "AUTHENTICATION_ERROR"

    token_response = client.post(
        reverse("token-obtain-pair"),
        {"email": user.email, "password": "strong-password"},
        format="json",
    )
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_response.data['access']}")
    authenticated_response = client.get(url)

    assert authenticated_response.status_code == 200
    assert authenticated_response.data["email"] == user.email


def test_pagination_has_default_and_bounded_client_page_size():
    paginator = StandardResultsPagination()
    request = Request(APIRequestFactory().get("/api/v1/example/?page_size=999"))
    page = paginator.paginate_queryset(list(range(150)), request)

    assert paginator.page_size == 25
    assert paginator.max_page_size == 100
    assert len(page) == 100


@pytest.mark.django_db
def test_openapi_schema_includes_authentication_routes(client):
    response = client.get(reverse("schema"))

    assert response.status_code == 200
    schema = yaml.safe_load(response.content)
    assert "/api/v1/auth/token/" in schema["paths"]
    assert "/api/v1/auth/token/refresh/" in schema["paths"]
    assert "/api/v1/assets/" in schema["paths"]
    assert "/api/v1/assets/categories/" in schema["paths"]
    assert "/api/v1/assets/acquisitions/" in schema["paths"]
    assert "/api/v1/assets/acquisitions/{id}/capitalize/" in schema["paths"]
    asset_parameters = {
        parameter["name"] for parameter in schema["paths"]["/api/v1/assets/"]["get"]["parameters"]
    }
    assert {"status", "search", "ordering", "acquisition_date_after"} <= asset_parameters
    assert schema["paths"]["/api/v1/auth/me/"]["get"]["security"]
    assert any(
        security_scheme.get("type") == "http"
        and security_scheme.get("scheme", "").lower() == "bearer"
        for security_scheme in schema["components"]["securitySchemes"].values()
    )


def test_validation_errors_use_the_public_error_envelope():
    response = api_exception_handler(ValidationError({"name": ["This field is required."]}), {})

    assert response.status_code == 400
    assert response.data == {
        "success": False,
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "The request contains invalid fields.",
            "details": {"name": ["This field is required."]},
        },
    }
