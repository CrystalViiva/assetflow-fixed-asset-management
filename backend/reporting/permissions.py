from rest_framework.permissions import BasePermission

from accounts.models import UserRole
from reporting.models import ReportType
from reporting.selectors import available_report_types


class ReportingPermission(BasePermission):
    """Report access is explicitly limited to users with at least one report type."""

    def has_permission(self, request, view):
        user = request.user
        return bool(user.is_authenticated and user.organization_id and available_report_types(user))

    def has_object_permission(self, request, view, obj):
        user = request.user
        return (
            obj.organization_id == user.organization_id
            and obj.report_type in available_report_types(user)
            and (
                user.role != UserRole.DEPARTMENT_MANAGER
                or obj.scope_department_id == user.department_id
            )
            and (
                user.role != UserRole.ACCOUNTANT
                or obj.report_type
                not in {
                    ReportType.ASSURANCE_RUNS,
                    ReportType.ASSURANCE_FINDINGS,
                    ReportType.ASSURANCE_OCCURRENCES,
                }
                or obj.requested_role == UserRole.ACCOUNTANT
            )
        )
