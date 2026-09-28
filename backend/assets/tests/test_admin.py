import pytest
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory

from accounts.models import User
from assets.admin import AssetAdmin
from assets.models import Asset, AssetStatus


@pytest.mark.django_db
def test_active_asset_placement_is_read_only_for_tenant_admin(asset_manager, asset_factory):
    asset_manager.is_staff = True
    asset_manager.save(update_fields=("is_staff",))
    asset = asset_factory("AST-ADMIN-PLACEMENT", status=AssetStatus.ACTIVE)
    model_admin = AssetAdmin(Asset, AdminSite())
    request = RequestFactory().get("/admin/assets/asset/")
    request.user = asset_manager

    assert {"department", "location"}.issubset(set(model_admin.get_readonly_fields(request, asset)))


@pytest.mark.django_db
def test_global_superuser_retains_explicit_asset_correction_path(asset_factory):
    superuser = User.objects.create_superuser("asset-root@example.test", "test-password")
    asset = asset_factory("AST-ADMIN-GLOBAL-CORRECTION", status=AssetStatus.ACTIVE)
    model_admin = AssetAdmin(Asset, AdminSite())
    request = RequestFactory().get("/admin/assets/asset/")
    request.user = superuser

    assert "department" not in model_admin.get_readonly_fields(request, asset)
    assert "location" not in model_admin.get_readonly_fields(request, asset)
