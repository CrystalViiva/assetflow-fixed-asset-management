"""Tenant-scoped and eager-loaded depreciation queries."""

from depreciation.models import AccountingPeriod, DepreciationEntry, DepreciationSchedule


def periods_for_organization(organization):
    return AccountingPeriod.objects.filter(
        organization_id=getattr(organization, "pk", organization)
    )


def schedules_for_organization(organization):
    return DepreciationSchedule.objects.filter(
        organization_id=getattr(organization, "pk", organization)
    ).select_related("organization", "asset", "asset__department")


def entries_for_organization(organization):
    return DepreciationEntry.objects.filter(
        organization_id=getattr(organization, "pk", organization)
    ).select_related(
        "organization", "asset", "asset__department", "schedule", "accounting_period", "created_by"
    )
