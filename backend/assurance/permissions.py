from rest_framework.permissions import SAFE_METHODS, BasePermission

from accounts.models import UserRole

READ_ROLES = {
    UserRole.ADMIN,
    UserRole.ASSET_MANAGER,
    UserRole.ACCOUNTANT,
    UserRole.DEPARTMENT_MANAGER,
}
MANAGE_ROLES = {UserRole.ADMIN, UserRole.ASSET_MANAGER}


class AssurancePermission(BasePermission):
    """Use AssetFlow roles; queryset selectors apply organization and functional scope."""

    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated or not user.organization_id:
            return False
        if request.method in SAFE_METHODS:
            return user.is_superuser or user.role in READ_ROLES
        return user.is_superuser or user.role in MANAGE_ROLES

    def has_object_permission(self, request, view, obj):
        if getattr(obj, "organization_id", None) != request.user.organization_id:
            return False
        if request.method not in SAFE_METHODS:
            return request.user.is_superuser or request.user.role in MANAGE_ROLES
        if request.user.role == UserRole.DEPARTMENT_MANAGER:
            asset_in_department = bool(
                request.user.department_id
                and getattr(obj, "asset_id", None)
                and obj.asset.department_id == request.user.department_id
            )
            verification = getattr(obj, "physical_verification", None)
            observation_in_department = bool(
                request.user.department_id
                and verification
                and verification.observed_department_id == request.user.department_id
            )
            return asset_in_department or observation_in_department
        if request.user.role == UserRole.ACCOUNTANT:
            return True
        return request.user.is_superuser or request.user.role in READ_ROLES
