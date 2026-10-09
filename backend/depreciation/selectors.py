"""Tenant-scoped and eager-loaded depreciation queries."""

from assets.models import AssetStatus
from commercial.entitlements import write_enabled_organizations
from depreciation.models import (
    AccountingPeriod,
    DepreciationEntry,
    DepreciationSchedule,
    ScheduleStatus,
)
from organizations.models import Organization


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


def active_organizations_for_depreciation():
    """Active organizations whose current commercial access permits financial writes."""
    return write_enabled_organizations(Organization.objects.all()).order_by("pk")


def schedules_due_for_period(organization, period):
    """Active schedules whose commencement month is not after the target month."""
    return (
        DepreciationSchedule.objects.filter(
            organization_id=getattr(organization, "pk", organization),
            status=ScheduleStatus.ACTIVE,
            asset__status=AssetStatus.ACTIVE,
            start_date__lte=period.last_day,
        )
        .select_related("organization", "asset")
        .order_by("asset__asset_tag", "asset_id")
    )
