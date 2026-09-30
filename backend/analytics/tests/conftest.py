import pytest
from django.test import override_settings

from accounts.models import User, UserRole
from organizations.models import Organization


@pytest.fixture
def manager(db):
    organization = Organization.objects.create(name="Analytics Org", code="ANL")
    return User.objects.create_user(
        "analytics-manager@example.test",
        "test-only-password",
        organization=organization,
        role=UserRole.ASSET_MANAGER,
    )


@pytest.fixture
def other_organization(db):
    return Organization.objects.create(name="Other Analytics Org", code="OANL")


@pytest.fixture
def analytics_storage(tmp_path):
    storages = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
        "assetflow_private": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
            "OPTIONS": {"location": str(tmp_path / "private")},
        },
        "assetflow_analytics": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
            "OPTIONS": {"location": str(tmp_path / "analytics")},
        },
    }
    with override_settings(STORAGES=storages):
        yield tmp_path / "analytics"
