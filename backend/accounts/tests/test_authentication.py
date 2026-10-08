from types import SimpleNamespace

import pytest
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication

from accounts.authentication import OrganizationJWTAuthentication


def test_organization_jwt_authentication_rejects_suspended_tenant(monkeypatch):
    user = SimpleNamespace(
        organization_id="org-1",
        is_superuser=False,
        organization=SimpleNamespace(is_active=False),
    )
    monkeypatch.setattr(JWTAuthentication, "get_user", lambda _self, _token: user)

    with pytest.raises(AuthenticationFailed):
        OrganizationJWTAuthentication().get_user({})


def test_organization_jwt_authentication_allows_active_tenant_and_unscoped_operator(monkeypatch):
    active_user = SimpleNamespace(
        organization_id="org-1",
        is_superuser=False,
        organization=SimpleNamespace(is_active=True),
    )
    monkeypatch.setattr(JWTAuthentication, "get_user", lambda _self, _token: active_user)

    assert OrganizationJWTAuthentication().get_user({}) is active_user

    operator = SimpleNamespace(organization_id=None, is_superuser=True)
    monkeypatch.setattr(JWTAuthentication, "get_user", lambda _self, _token: operator)

    assert OrganizationJWTAuthentication().get_user({}) is operator
