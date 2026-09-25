"""Organization-scoped disposal read queries."""

from disposals.models import Disposal


def disposals_for_organization(organization, user):
    queryset = Disposal.objects.filter(organization_id=organization).select_related(
        "organization",
        "asset",
        "asset__department",
        "asset__location",
        "requested_by",
        "submitted_by",
        "approved_by",
        "rejected_by",
        "cancelled_by",
        "created_by",
        "updated_by",
    )
    if user.role == "DEPARTMENT_MANAGER":
        if not user.department_id:
            return queryset.none()
        queryset = queryset.filter(asset__department_id=user.department_id)
    return queryset
