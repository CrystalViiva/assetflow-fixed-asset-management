from django.db.models import Exists, OuterRef

from maintenance.models import MaintenanceCost, MaintenancePlan, MaintenanceRecord, WorkOrder


def _visible_assets(queryset, user, asset_path="asset"):
    if user.role == "DEPARTMENT_MANAGER":
        if not user.department_id:
            return queryset.none()
        return queryset.filter(**{f"{asset_path}__department_id": user.department_id})
    if user.role == "EMPLOYEE":
        from transfers.models import AssetAssignment

        active_assignment = AssetAssignment.objects.filter(
            asset_id=OuterRef(f"{asset_path}_id"), assigned_to_id=user.pk, returned_at__isnull=True
        )
        return queryset.annotate(_assigned_to_user=Exists(active_assignment)).filter(
            _assigned_to_user=True
        )
    return queryset


def plans_for_organization(organization, user):
    queryset = MaintenancePlan.objects.filter(organization_id=organization).select_related(
        "organization", "asset", "asset__department", "created_by"
    )
    return _visible_assets(queryset, user)


def work_orders_for_organization(organization, user):
    queryset = WorkOrder.objects.filter(organization_id=organization).select_related(
        "organization", "asset", "asset__department", "requested_by", "assigned_to"
    )
    return _visible_assets(queryset, user)


def costs_for_organization(organization, user):
    queryset = MaintenanceCost.objects.filter(organization_id=organization).select_related(
        "organization", "work_order", "work_order__asset", "created_by"
    )
    if user.role in {"DEPARTMENT_MANAGER", "EMPLOYEE"}:
        return _visible_assets(queryset, user, "work_order__asset")
    return queryset


def records_for_organization(organization, user):
    queryset = MaintenanceRecord.objects.filter(organization_id=organization).select_related(
        "organization", "asset", "asset__department", "work_order", "performed_by"
    )
    return _visible_assets(queryset, user)
