from rest_framework.permissions import SAFE_METHODS, BasePermission

from accounts.models import UserRole


class DepreciationPermission(BasePermission):
    """Accounting roles administer postings; department managers receive scoped reads."""

    write_roles = {UserRole.ADMIN, UserRole.ASSET_MANAGER, UserRole.ACCOUNTANT}
    read_roles = write_roles | {UserRole.DEPARTMENT_MANAGER}

    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated or not user.organization_id:
            return False
        return user.role in (
            self.read_roles if request.method in SAFE_METHODS else self.write_roles
        )

    def has_object_permission(self, request, view, obj):
        if getattr(obj, "organization_id", None) != request.user.organization_id:
            return False
        if request.user.role == UserRole.DEPARTMENT_MANAGER:
            asset = getattr(obj, "asset", None)
            return asset is None or asset.department_id == request.user.department_id
        return True
