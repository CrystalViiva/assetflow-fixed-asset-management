"""Organization-scoped custody and transfer selectors."""

from django.db.models import Q

from transfers.models import AssetAssignment, AssetTransfer


def assignments_for_organization(organization):
    org_id = getattr(organization, "pk", organization)
    return AssetAssignment.objects.filter(organization_id=org_id).select_related(
        "organization",
        "asset",
        "asset__category",
        "assigned_to",
        "department",
        "location",
        "created_by",
        "returned_by",
    )


def transfers_for_organization(organization):
    org_id = getattr(organization, "pk", organization)
    return AssetTransfer.objects.filter(organization_id=org_id).select_related(
        "organization",
        "asset",
        "asset__department",
        "asset__location",
        "from_department",
        "from_location",
        "to_department",
        "to_location",
        "requested_by",
        "approved_by",
        "completed_by",
        "rejected_by",
        "cancelled_by",
    )


def visible_assignments(queryset, user):
    if user.role == "DEPARTMENT_MANAGER":
        return (
            queryset.filter(department_id=user.department_id)
            if user.department_id
            else queryset.none()
        )
    if user.role == "EMPLOYEE":
        return queryset.filter(assigned_to_id=user.pk)
    return queryset


def visible_transfers(queryset, user):
    if user.role == "DEPARTMENT_MANAGER":
        if not user.department_id:
            return queryset.none()
        return queryset.filter(
            Q(from_department_id=user.department_id) | Q(to_department_id=user.department_id)
        )
    if user.role == "EMPLOYEE":
        return queryset.filter(
            asset__assignments__assigned_to_id=user.pk,
            asset__assignments__returned_at__isnull=True,
        ).distinct()
    return queryset
