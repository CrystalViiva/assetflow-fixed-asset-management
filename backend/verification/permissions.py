from rest_framework.permissions import SAFE_METHODS, BasePermission

from accounts.models import UserRole

READ_ROLES = {
    UserRole.ADMIN,
    UserRole.ASSET_MANAGER,
    UserRole.ACCOUNTANT,
    UserRole.DEPARTMENT_MANAGER,
}
MANAGE_ROLES = {UserRole.ADMIN, UserRole.ASSET_MANAGER}


class VerificationPermission(BasePermission):
    """Role gate; selectors and services enforce tenant and department boundaries."""

    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated or not user.organization_id:
            return False
        if request.method in SAFE_METHODS:
            return user.is_superuser or user.role in READ_ROLES
        if user.is_superuser or user.role in MANAGE_ROLES:
            return True
        return (
            user.role == UserRole.DEPARTMENT_MANAGER
            and view.basename == "verification-record"
            and view.action == "create"
        )

    def has_object_permission(self, request, view, obj):
        organization_id = getattr(obj, "organization_id", None)
        if organization_id != request.user.organization_id:
            return False
        if request.method in SAFE_METHODS:
            if request.user.role != UserRole.DEPARTMENT_MANAGER:
                return request.user.is_superuser or request.user.role in READ_ROLES
            department_id = request.user.department_id
            if not department_id:
                return False
            if hasattr(obj, "scope_type"):
                return obj.scope_type == "DEPARTMENT" and obj.department_id == department_id
            if hasattr(obj, "verification"):
                obj = obj.verification
            if hasattr(obj, "observed_department_id"):
                return bool(
                    (
                        obj.campaign.scope_type == "DEPARTMENT"
                        and obj.campaign.department_id == department_id
                    )
                    or obj.observed_department_id == department_id
                    or (obj.asset_id and obj.asset.department_id == department_id)
                )
            return False
        return request.user.is_superuser or request.user.role in MANAGE_ROLES
