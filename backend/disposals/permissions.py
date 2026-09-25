from rest_framework.permissions import SAFE_METHODS, BasePermission

from accounts.models import UserRole

DISPOSAL_READ_ROLES = {
    UserRole.ADMIN,
    UserRole.ASSET_MANAGER,
    UserRole.ACCOUNTANT,
    UserRole.DEPARTMENT_MANAGER,
}
DISPOSAL_WRITE_ROLES = {UserRole.ADMIN, UserRole.ASSET_MANAGER}


class DisposalPermission(BasePermission):
    """Organization-scoped disposal read access and controlled role mutations."""

    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated or not user.organization_id:
            return False
        if request.method in SAFE_METHODS:
            return user.is_superuser or user.role in DISPOSAL_READ_ROLES
        return user.is_superuser or user.role in DISPOSAL_WRITE_ROLES

    def has_object_permission(self, request, view, obj):
        if obj.organization_id != request.user.organization_id:
            return False
        if request.method not in SAFE_METHODS:
            return request.user.is_superuser or request.user.role in DISPOSAL_WRITE_ROLES
        if request.user.role == UserRole.DEPARTMENT_MANAGER:
            return bool(
                request.user.department_id and obj.asset.department_id == request.user.department_id
            )
        return request.user.is_superuser or request.user.role in DISPOSAL_READ_ROLES
