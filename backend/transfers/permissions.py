from rest_framework.permissions import SAFE_METHODS, BasePermission

from accounts.models import UserRole

WRITE_ROLES = {UserRole.ADMIN, UserRole.ASSET_MANAGER}
READ_ROLES = set(UserRole.values)


class CustodyTransferPermission(BasePermission):
    """Organization membership plus role-controlled workflow mutations."""

    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated or not user.organization_id:
            return False
        if request.method in SAFE_METHODS:
            return user.is_superuser or user.role in READ_ROLES
        return user.is_superuser or user.role in WRITE_ROLES

    def has_object_permission(self, request, view, obj):
        if obj.organization_id != request.user.organization_id:
            return False
        if request.method not in SAFE_METHODS:
            return request.user.is_superuser or request.user.role in WRITE_ROLES
        if request.user.is_superuser or request.user.role in {
            UserRole.ADMIN,
            UserRole.ASSET_MANAGER,
            UserRole.ACCOUNTANT,
        }:
            return True
        if request.user.role == UserRole.DEPARTMENT_MANAGER:
            if not request.user.department_id:
                return False
            if hasattr(obj, "assigned_to_id"):
                return obj.department_id == request.user.department_id
            return (
                obj.from_department_id == request.user.department_id
                or obj.to_department_id == request.user.department_id
            )
        if request.user.role == UserRole.EMPLOYEE:
            if hasattr(obj, "assigned_to_id"):
                return obj.assigned_to_id == request.user.pk
            return obj.asset.assignments.filter(
                assigned_to_id=request.user.pk, returned_at__isnull=True
            ).exists()
        return False
