from rest_framework.permissions import SAFE_METHODS, BasePermission

from accounts.models import UserRole

ASSET_MANAGEMENT_ROLES = {UserRole.ADMIN, UserRole.ASSET_MANAGER}


class AssetDomainPermission(BasePermission):
    """Require organization membership; limit writes to asset administrators."""

    message = "You do not have permission to manage asset master data."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated or not user.organization_id:
            return False
        if request.method in SAFE_METHODS:
            return True
        return user.is_superuser or user.role in ASSET_MANAGEMENT_ROLES

    def has_object_permission(self, request, view, obj):
        if obj.organization_id != request.user.organization_id:
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_superuser or request.user.role in ASSET_MANAGEMENT_ROLES
