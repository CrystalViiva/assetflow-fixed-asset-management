from rest_framework.permissions import SAFE_METHODS, BasePermission

from accounts.models import UserRole

WRITE_ROLES = {UserRole.ADMIN, UserRole.ASSET_MANAGER}


class MaintenancePermission(BasePermission):
    """Role gate; tenant and department visibility are enforced by selectors."""

    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated or not user.organization_id:
            return False
        if request.method in SAFE_METHODS:
            return user.is_superuser or user.role in UserRole.values
        return user.is_superuser or user.role in WRITE_ROLES

    def has_object_permission(self, request, view, obj):
        if obj.organization_id != request.user.organization_id:
            return False
        return (
            request.method in SAFE_METHODS
            or request.user.is_superuser
            or request.user.role in WRITE_ROLES
        )
