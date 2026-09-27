"""Tenant- and role-scoped assurance query and reporting selectors."""

from django.db.models import Count, Q, Sum

from accounts.models import UserRole
from assurance.models import (
    ACTIVE_FINDING_STATUSES,
    AssuranceFinding,
    AssuranceRun,
    AssuranceRunType,
    FindingStatus,
    FindingType,
)

FINANCIAL_FINDING_TYPES = (
    FindingType.DISPOSAL_STATUS_MISMATCH,
    FindingType.DEPRECIATION_EXCEPTION,
    FindingType.BOOK_VALUE_EXCEPTION,
)
OPERATIONAL_FINDING_TYPES = tuple(
    value for value in FindingType.values if value not in FINANCIAL_FINDING_TYPES
)


def runs_for_user(organization, user):
    queryset = AssuranceRun.objects.filter(organization_id=organization).select_related(
        "organization", "started_by", "completed_by", "verification_campaign"
    )
    if user.role == UserRole.ACCOUNTANT:
        queryset = queryset.filter(run_type=AssuranceRunType.FINANCIAL)
    elif user.role == UserRole.DEPARTMENT_MANAGER:
        return queryset.none()
    return queryset


def findings_for_user(organization, user):
    queryset = AssuranceFinding.objects.filter(organization_id=organization).select_related(
        "organization",
        "assurance_run",
        "last_detected_run",
        "asset",
        "asset__department",
        "asset__location",
        "physical_verification",
        "physical_verification__observed_department",
        "resolved_by",
    )
    if user.role == UserRole.ACCOUNTANT:
        return queryset.filter(finding_type__in=FINANCIAL_FINDING_TYPES)
    if user.role == UserRole.DEPARTMENT_MANAGER:
        if not user.department_id:
            return queryset.none()
        return queryset.filter(
            Q(asset__department_id=user.department_id)
            | Q(physical_verification__observed_department_id=user.department_id)
        ).distinct()
    return queryset


def run_findings_for_user(run, user):
    queryset = findings_for_user(run.organization_id, user)
    return queryset.filter(occurrences__assurance_run=run).distinct()


def run_progress(run):
    return {
        "status": run.status,
        "assets_evaluated": run.assets_evaluated,
        "findings_generated": run.findings_generated,
        "findings_open": run.findings_open,
        "findings_resolved": run.findings_resolved,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
    }


def assurance_summary(organization, user):
    findings = findings_for_user(organization, user)
    runs = runs_for_user(organization, user)
    run_totals = runs.aggregate(assets_evaluated=Sum("assets_evaluated"))
    by_severity = list(findings.values("severity").annotate(count=Count("pk")).order_by("severity"))
    by_type = list(
        findings.values("finding_type").annotate(count=Count("pk")).order_by("finding_type")
    )
    by_status = list(findings.values("status").annotate(count=Count("pk")).order_by("status"))
    multi_asset_count = (
        findings.filter(asset__isnull=False)
        .values("asset_id")
        .annotate(total=Count("pk"))
        .filter(total__gt=1)
        .count()
    )
    return {
        "runs": runs.count(),
        "assets_evaluated": run_totals["assets_evaluated"] or 0,
        "total_findings": findings.count(),
        "findings_open": findings.filter(status__in=ACTIVE_FINDING_STATUSES).count(),
        "findings_resolved": findings.filter(status=FindingStatus.RESOLVED).count(),
        "recurring_findings": findings.filter(occurrence_count__gt=1).count(),
        "assets_with_multiple_findings": multi_asset_count,
        "by_severity": by_severity,
        "by_type": by_type,
        "by_status": by_status,
    }
