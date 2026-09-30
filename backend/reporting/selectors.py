"""Tenant-, role-, and department-scoped operational report selectors."""

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from decimal import Decimal
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import DateTimeField, Q, Sum
from django.utils import timezone
from django.utils.dateparse import parse_date

from accounts.models import UserRole
from assets.models import Acquisition, Asset
from assurance.models import AssuranceFinding, AssuranceFindingOccurrence, AssuranceRun
from audit.models import AuditLog
from depreciation.models import AccountingPeriod, DepreciationEntry
from disposals.models import Disposal
from maintenance.models import MaintenanceCost, MaintenanceRecord, WorkOrder
from organizations.models import Department
from reporting.models import ReportSnapshot, ReportType
from transfers.models import AssetAssignment, AssetTransfer
from verification.models import (
    PhysicalVerification,
    VerificationCampaign,
    VerificationException,
)

MANAGER_REPORTS = frozenset(ReportType.values)
ACCOUNTANT_REPORTS = frozenset(
    {
        ReportType.ASSET_REGISTER,
        ReportType.ACQUISITIONS,
        ReportType.DEPRECIATION,
        ReportType.ACCOUNTING_PERIODS,
        ReportType.DISPOSALS,
        ReportType.ASSURANCE_RUNS,
        ReportType.ASSURANCE_FINDINGS,
        ReportType.ASSURANCE_OCCURRENCES,
    }
)
DEPARTMENT_REPORTS = frozenset(
    {
        ReportType.ASSET_REGISTER,
        ReportType.ACQUISITIONS,
        ReportType.DEPRECIATION,
        ReportType.ASSIGNMENTS,
        ReportType.TRANSFERS,
        ReportType.WORK_ORDERS,
        ReportType.MAINTENANCE_COSTS,
        ReportType.MAINTENANCE_RECORDS,
        ReportType.DISPOSALS,
        ReportType.VERIFICATION_CAMPAIGNS,
        ReportType.VERIFICATION_RECORDS,
        ReportType.VERIFICATION_EXCEPTIONS,
        ReportType.ASSURANCE_FINDINGS,
        ReportType.ASSURANCE_OCCURRENCES,
    }
)


@dataclass(frozen=True)
class ReportDefinition:
    label: str
    queryset_name: str
    fields: dict[str, str]
    search_fields: tuple[str, ...] = ()
    department_filter: str | None = None
    date_field: str | None = None
    status_field: str | None = None
    summary_fields: tuple[str, ...] = ()


DEFINITIONS = {
    ReportType.ASSET_REGISTER: ReportDefinition(
        "Asset register",
        "assets",
        {
            "id": "pk",
            "asset_tag": "asset_tag",
            "name": "name",
            "status": "status",
            "condition": "condition",
            "category": "category__name",
            "department": "department__name",
            "department_id": "department_id",
            "location": "location__name",
            "purchase_cost": "purchase_cost",
            "accumulated_depreciation": "accumulated_depreciation",
            "current_book_value": "current_book_value",
            "capitalization_date": "capitalization_date",
            "available_for_use_date": "available_for_use_date",
        },
        ("asset_tag", "name", "serial_number"),
        "department_id",
        status_field="status",
        summary_fields=("purchase_cost", "accumulated_depreciation", "current_book_value"),
    ),
    ReportType.ACQUISITIONS: ReportDefinition(
        "Acquisitions and capitalization",
        "acquisitions",
        {
            "id": "pk",
            "asset_tag": "asset__asset_tag",
            "asset_name": "asset__name",
            "department": "asset__department__name",
            "department_id": "asset__department_id",
            "vendor_name": "vendor_name",
            "invoice_number": "invoice_number",
            "acquisition_date": "acquisition_date",
            "capitalization_date": "capitalization_date",
            "currency": "currency",
            "purchase_price": "purchase_price",
            "freight_cost": "freight_cost",
            "installation_cost": "installation_cost",
            "civil_works_cost": "civil_works_cost",
            "other_capitalizable_cost": "other_capitalizable_cost",
            "total_cost": "total_cost",
            "status": "status",
        },
        ("asset__asset_tag", "asset__name", "vendor_name", "invoice_number", "reference"),
        "asset__department_id",
        "acquisition_date",
        "status",
        ("total_cost",),
    ),
    ReportType.DEPRECIATION: ReportDefinition(
        "Depreciation ledger",
        "depreciation",
        {
            "id": "pk",
            "asset_tag": "asset__asset_tag",
            "department": "asset__department__name",
            "department_id": "asset__department_id",
            "year": "accounting_period__year",
            "month": "accounting_period__month",
            "opening_book_value": "opening_book_value",
            "depreciation_amount": "depreciation_amount",
            "accumulated_depreciation": "accumulated_depreciation",
            "closing_book_value": "closing_book_value",
            "posted_at": "posted_at",
        },
        ("asset__asset_tag",),
        "asset__department_id",
        "posted_at",
        summary_fields=("depreciation_amount",),
    ),
    ReportType.ACCOUNTING_PERIODS: ReportDefinition(
        "Accounting periods",
        "periods",
        {
            "id": "pk",
            "year": "year",
            "month": "month",
            "status": "status",
            "opened_at": "opened_at",
            "closed_at": "closed_at",
        },
        date_field="opened_at",
        status_field="status",
    ),
    ReportType.ASSIGNMENTS: ReportDefinition(
        "Assignments and custody",
        "assignments",
        {
            "id": "pk",
            "asset_tag": "asset__asset_tag",
            "asset_name": "asset__name",
            "assigned_to": "assigned_to__email",
            "department": "department__name",
            "department_id": "department_id",
            "location": "location__name",
            "assigned_at": "assigned_at",
            "returned_at": "returned_at",
        },
        ("asset__asset_tag", "asset__name", "assigned_to__email"),
        "department_id",
        "assigned_at",
    ),
    ReportType.TRANSFERS: ReportDefinition(
        "Transfers",
        "transfers",
        {
            "id": "pk",
            "asset_tag": "asset__asset_tag",
            "status": "status",
            "from_department": "from_department__name",
            "from_department_id": "from_department_id",
            "to_department": "to_department__name",
            "to_department_id": "to_department_id",
            "from_location": "from_location__name",
            "to_location": "to_location__name",
            "requested_at": "requested_at",
            "completed_at": "completed_at",
            "reason": "reason",
        },
        ("asset__asset_tag", "reason"),
        date_field="requested_at",
        status_field="status",
    ),
    ReportType.WORK_ORDERS: ReportDefinition(
        "Maintenance work orders",
        "work_orders",
        {
            "id": "pk",
            "work_order_number": "work_order_number",
            "asset_tag": "asset__asset_tag",
            "department": "asset__department__name",
            "department_id": "asset__department_id",
            "maintenance_type": "maintenance_type",
            "priority": "priority",
            "status": "status",
            "due_date": "due_date",
            "opened_at": "opened_at",
            "completed_at": "completed_at",
        },
        ("work_order_number", "asset__asset_tag", "description"),
        "asset__department_id",
        "opened_at",
        "status",
    ),
    ReportType.MAINTENANCE_COSTS: ReportDefinition(
        "Maintenance costs",
        "maintenance_costs",
        {
            "id": "pk",
            "work_order_number": "work_order__work_order_number",
            "asset_tag": "work_order__asset__asset_tag",
            "department": "work_order__asset__department__name",
            "department_id": "work_order__asset__department_id",
            "cost_type": "cost_type",
            "quantity": "quantity",
            "unit_cost": "unit_cost",
            "total_cost": "total_cost",
            "incurred_at": "incurred_at",
        },
        ("work_order__work_order_number", "work_order__asset__asset_tag", "description"),
        "work_order__asset__department_id",
        "incurred_at",
        summary_fields=("total_cost",),
    ),
    ReportType.MAINTENANCE_RECORDS: ReportDefinition(
        "Maintenance records",
        "maintenance_records",
        {
            "id": "pk",
            "asset_tag": "asset__asset_tag",
            "department": "asset__department__name",
            "department_id": "asset__department_id",
            "maintenance_type": "maintenance_type",
            "maintenance_date": "maintenance_date",
            "total_cost": "total_cost",
        },
        ("asset__asset_tag", "summary"),
        "asset__department_id",
        "maintenance_date",
    ),
    ReportType.DISPOSALS: ReportDefinition(
        "Disposals",
        "disposals",
        {
            "id": "pk",
            "asset_tag": "asset__asset_tag",
            "department": "asset__department__name",
            "department_id": "asset__department_id",
            "disposal_date": "disposal_date",
            "disposal_method": "disposal_method",
            "status": "status",
            "currency": "currency",
            "proceeds": "proceeds",
            "capitalized_cost_at_disposal": "capitalized_cost_at_disposal",
            "accumulated_depreciation_at_disposal": "accumulated_depreciation_at_disposal",
            "carrying_amount": "carrying_amount",
            "gain_or_loss": "gain_or_loss",
            "completed_at": "completed_at",
        },
        ("asset__asset_tag", "reason"),
        "asset__department_id",
        "disposal_date",
        "status",
        ("proceeds", "carrying_amount", "gain_or_loss"),
    ),
    ReportType.VERIFICATION_CAMPAIGNS: ReportDefinition(
        "Physical verification campaigns",
        "campaigns",
        {
            "id": "pk",
            "name": "name",
            "status": "status",
            "scope_type": "scope_type",
            "department": "department__name",
            "department_id": "department_id",
            "location": "location__name",
            "start_date": "start_date",
            "due_date": "due_date",
            "completed_at": "completed_at",
        },
        ("name", "description"),
        "department_id",
        "start_date",
        "status",
    ),
    ReportType.VERIFICATION_RECORDS: ReportDefinition(
        "Physical verification observations",
        "verifications",
        {
            "id": "pk",
            "campaign": "campaign__name",
            "asset_tag": "asset__asset_tag",
            "observed_asset_tag": "observed_asset_tag",
            "result": "result",
            "observed_condition": "observed_condition",
            "observed_department": "observed_department__name",
            "observed_department_id": "observed_department_id",
            "observed_location": "observed_location__name",
            "verified_at": "verified_at",
        },
        ("asset__asset_tag", "observed_asset_tag", "observed_description", "notes"),
        date_field="verified_at",
    ),
    ReportType.VERIFICATION_EXCEPTIONS: ReportDefinition(
        "Physical verification exceptions",
        "exceptions",
        {
            "id": "pk",
            "campaign": "campaign__name",
            "asset_tag": "asset__asset_tag",
            "department": "asset__department__name",
            "department_id": "asset__department_id",
            "exception_type": "exception_type",
            "severity": "severity",
            "status": "status",
            "created_at": "created_at",
            "resolved_at": "resolved_at",
        },
        ("asset__asset_tag", "description"),
        None,
        "created_at",
        "status",
    ),
    ReportType.ASSURANCE_RUNS: ReportDefinition(
        "Assurance runs",
        "assurance_runs",
        {
            "id": "pk",
            "run_type": "run_type",
            "status": "status",
            "scheduled_for": "scheduled_for",
            "started_at": "started_at",
            "completed_at": "completed_at",
            "assets_evaluated": "assets_evaluated",
            "findings_generated": "findings_generated",
            "findings_open": "findings_open",
            "findings_resolved": "findings_resolved",
        },
        date_field="created_at",
        status_field="status",
    ),
    ReportType.ASSURANCE_FINDINGS: ReportDefinition(
        "Assurance findings",
        "assurance_findings",
        {
            "id": "pk",
            "asset_tag": "asset__asset_tag",
            "finding_type": "finding_type",
            "severity": "severity",
            "status": "status",
            "source": "source",
            "occurrence_count": "occurrence_count",
            "first_detected_at": "first_detected_at",
            "last_detected_at": "last_detected_at",
        },
        ("asset__asset_tag", "description", "expected_value", "observed_value"),
        date_field="first_detected_at",
        status_field="status",
    ),
    ReportType.ASSURANCE_OCCURRENCES: ReportDefinition(
        "Assurance finding occurrences",
        "assurance_occurrences",
        {
            "id": "pk",
            "finding_id": "finding_id",
            "asset_tag": "finding__asset__asset_tag",
            "finding_type": "finding__finding_type",
            "severity": "finding__severity",
            "run_id": "assurance_run_id",
            "detected_at": "detected_at",
            "description": "description",
        },
        ("finding__asset__asset_tag", "description"),
        date_field="detected_at",
    ),
    ReportType.LIFECYCLE_HISTORY: ReportDefinition(
        "Lifecycle audit history",
        "audit_logs",
        {
            "id": "pk",
            "timestamp": "timestamp",
            "action": "action",
            "entity_type": "entity_type",
            "entity_id": "entity_id",
            "user_email": "user__email",
        },
        ("action", "entity_type", "entity_id"),
        date_field="timestamp",
    ),
}

QUERYSETS = {
    "assets": Asset.objects,
    "acquisitions": Acquisition.objects,
    "depreciation": DepreciationEntry.objects,
    "periods": AccountingPeriod.objects,
    "assignments": AssetAssignment.objects,
    "transfers": AssetTransfer.objects,
    "work_orders": WorkOrder.objects,
    "maintenance_costs": MaintenanceCost.objects,
    "maintenance_records": MaintenanceRecord.objects,
    "disposals": Disposal.objects,
    "campaigns": VerificationCampaign.objects,
    "verifications": PhysicalVerification.objects,
    "exceptions": VerificationException.objects,
    "assurance_runs": AssuranceRun.objects,
    "assurance_findings": AssuranceFinding.objects,
    "assurance_occurrences": AssuranceFindingOccurrence.objects,
    "audit_logs": AuditLog.objects,
}


def available_report_types(user):
    if user.role in {UserRole.ADMIN, UserRole.ASSET_MANAGER} or user.is_superuser:
        return MANAGER_REPORTS
    if user.role == UserRole.ACCOUNTANT:
        return ACCOUNTANT_REPORTS
    if user.role == UserRole.DEPARTMENT_MANAGER:
        return DEPARTMENT_REPORTS if user.department_id else frozenset()
    return frozenset()


def snapshots_for_user(user):
    queryset = ReportSnapshot.objects.filter(
        organization_id=user.organization_id,
        report_type__in=available_report_types(user),
    )
    if user.role == UserRole.DEPARTMENT_MANAGER:
        queryset = queryset.filter(scope_department_id=user.department_id)
    if user.role == UserRole.ACCOUNTANT:
        restricted_types = (
            ReportType.ASSURANCE_RUNS,
            ReportType.ASSURANCE_FINDINGS,
            ReportType.ASSURANCE_OCCURRENCES,
        )
        queryset = queryset.filter(
            ~Q(report_type__in=restricted_types) | Q(requested_role=UserRole.ACCOUNTANT)
        )
    return queryset


def supported_filters(report_type):
    definition = DEFINITIONS[report_type]
    names = []
    if definition.department_filter or report_type in {
        ReportType.TRANSFERS,
        ReportType.VERIFICATION_RECORDS,
        ReportType.VERIFICATION_EXCEPTIONS,
        ReportType.ASSURANCE_FINDINGS,
        ReportType.ASSURANCE_OCCURRENCES,
    }:
        names.append("department")
    if definition.status_field:
        names.append("status")
    if definition.date_field:
        names.extend(("date_from", "date_to"))
    if any(field.endswith("asset_tag") for field in definition.search_fields):
        names.append("asset_tag")
    if definition.search_fields:
        names.append("search")
    return names


def assert_report_access(report_type, user):
    if report_type not in DEFINITIONS or report_type not in available_report_types(user):
        raise PermissionDenied("This report is not available to your role.")


def _organization_queryset(report_type, organization_id, user):
    definition = DEFINITIONS[report_type]
    if report_type == ReportType.ASSURANCE_RUNS and user.role == UserRole.ACCOUNTANT:
        queryset = QUERYSETS[definition.queryset_name].filter(
            organization_id=organization_id, run_type="FINANCIAL"
        )
    elif report_type in {ReportType.ASSURANCE_FINDINGS, ReportType.ASSURANCE_OCCURRENCES}:
        if user.role == UserRole.ACCOUNTANT:
            queryset = QUERYSETS[definition.queryset_name].filter(
                organization_id=organization_id,
                **(
                    {
                        "finding__finding_type__in": (
                            "DISPOSAL_STATUS_MISMATCH",
                            "DEPRECIATION_EXCEPTION",
                            "BOOK_VALUE_EXCEPTION",
                        )
                    }
                    if report_type == ReportType.ASSURANCE_OCCURRENCES
                    else {
                        "finding_type__in": (
                            "DISPOSAL_STATUS_MISMATCH",
                            "DEPRECIATION_EXCEPTION",
                            "BOOK_VALUE_EXCEPTION",
                        )
                    }
                ),
            )
        else:
            queryset = QUERYSETS[definition.queryset_name].filter(organization_id=organization_id)
    else:
        queryset = QUERYSETS[definition.queryset_name].filter(organization_id=organization_id)
    return queryset


def _department_scope(queryset, report_type, department_id):
    if not department_id:
        return queryset
    path = DEFINITIONS[report_type].department_filter
    if path:
        return queryset.filter(**{path: department_id})
    if report_type == ReportType.TRANSFERS:
        return queryset.filter(
            Q(from_department_id=department_id) | Q(to_department_id=department_id)
        )
    if report_type in {ReportType.VERIFICATION_RECORDS, ReportType.VERIFICATION_EXCEPTIONS}:
        campaign_path = "campaign__department_id"
        asset_path = "asset__department_id"
        observed_path = (
            "observed_department_id"
            if report_type == ReportType.VERIFICATION_RECORDS
            else "verification__observed_department_id"
        )
        return queryset.filter(
            Q(**{campaign_path: department_id})
            | Q(**{asset_path: department_id})
            | Q(**{observed_path: department_id})
        ).distinct()
    if report_type == ReportType.ASSURANCE_FINDINGS:
        return queryset.filter(
            Q(asset__department_id=department_id)
            | Q(physical_verification__observed_department_id=department_id)
        ).distinct()
    if report_type == ReportType.ASSURANCE_OCCURRENCES:
        return queryset.filter(
            Q(finding__asset__department_id=department_id)
            | Q(finding__physical_verification__observed_department_id=department_id)
        ).distinct()
    return queryset.none()


def _validated_filters(report_type, filters, user, *, scope_department_id=None):
    if not isinstance(filters, dict):
        raise ValidationError({"filters": "Filters must be a JSON object."})
    allowed = {"department", "status", "date_from", "date_to", "asset_tag", "search"}
    unknown = sorted(set(filters) - allowed)
    if unknown:
        raise ValidationError({"filters": f"Unsupported filters: {', '.join(unknown)}."})
    for name, value in filters.items():
        if not isinstance(value, str):
            raise ValidationError({name: "Enter a string value."})
        if len(value) > 200:
            raise ValidationError({name: "Keep filter values to 200 characters or fewer."})

    definition = DEFINITIONS[report_type]
    department_id = scope_department_id
    if "department" in filters:
        try:
            requested_department_id = UUID(str(filters["department"]))
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValidationError({"department": "Enter a valid department ID."}) from exc
        if (
            user.role == UserRole.DEPARTMENT_MANAGER
            and requested_department_id != user.department_id
        ):
            raise ValidationError({"department": "This department is outside your scope."})
        if definition.department_filter is None and report_type not in {
            ReportType.TRANSFERS,
            ReportType.VERIFICATION_RECORDS,
            ReportType.VERIFICATION_EXCEPTIONS,
            ReportType.ASSURANCE_FINDINGS,
            ReportType.ASSURANCE_OCCURRENCES,
        }:
            raise ValidationError({"department": "Department filtering is not supported."})
        department_id = requested_department_id

    return definition, department_id


def _is_datetime_field(queryset, field_path):
    model = queryset.model
    field = None
    for name in field_path.split("__"):
        field = model._meta.get_field(name)
        if field.is_relation:
            model = field.related_model
    return isinstance(field, DateTimeField)


def report_queryset(report_type, organization_id, user, filters=None, *, scope_department_id=None):
    """Return the report's current-state query, with all tenant/role scope applied first."""
    assert_report_access(report_type, user)
    filters = filters or {}
    definition, department_id = _validated_filters(
        report_type, filters, user, scope_department_id=scope_department_id
    )
    queryset = _organization_queryset(report_type, organization_id, user)
    if user.role == UserRole.DEPARTMENT_MANAGER and department_id is None:
        department_id = user.department_id
    if (
        department_id
        and not Department.objects.filter(
            pk=department_id, organization_id=organization_id
        ).exists()
    ):
        raise ValidationError({"department": "Select a department in your organization."})
    queryset = _department_scope(queryset, report_type, department_id)

    for name, comparator in (("date_from", "gte"), ("date_to", "lte")):
        value = filters.get(name)
        if value:
            parsed = parse_date(str(value))
            if parsed is None:
                raise ValidationError({name: "Enter a valid ISO date (YYYY-MM-DD)."})
            if definition.date_field is None:
                raise ValidationError({name: "Date filtering is not supported."})
            if _is_datetime_field(queryset, definition.date_field):
                bound_date = parsed + timedelta(days=1) if comparator == "lte" else parsed
                bound = timezone.make_aware(
                    datetime.combine(bound_date, time.min), timezone.get_current_timezone()
                )
                lookup = "lt" if comparator == "lte" else "gte"
                queryset = queryset.filter(**{f"{definition.date_field}__{lookup}": bound})
                continue
            queryset = queryset.filter(**{f"{definition.date_field}__{comparator}": parsed})

    status = filters.get("status")
    if status:
        if definition.status_field is None:
            raise ValidationError({"status": "Status filtering is not supported."})
        valid_statuses = dict(queryset.model._meta.get_field(definition.status_field).choices)
        if valid_statuses and str(status) not in valid_statuses:
            raise ValidationError({"status": "Select a valid status for this report."})
        queryset = queryset.filter(**{definition.status_field: str(status)})

    asset_tag = filters.get("asset_tag")
    if asset_tag:
        tag_field = next(
            (field for field in definition.search_fields if field.endswith("asset_tag")), None
        )
        if not tag_field:
            raise ValidationError({"asset_tag": "Asset tag filtering is not supported."})
        queryset = queryset.filter(**{tag_field: str(asset_tag)})

    search = filters.get("search")
    if search:
        if not definition.search_fields:
            raise ValidationError({"search": "Search is not supported."})
        expression = Q()
        for field in definition.search_fields:
            expression |= Q(**{f"{field}__icontains": str(search)})
        queryset = queryset.filter(expression)

    return queryset.order_by("pk")


def report_rows(queryset, report_type):
    definition = DEFINITIONS[report_type]
    return queryset.values(*dict.fromkeys(definition.fields.values()))


def serialize_report_row(row, report_type):
    """Rename selected ORM fields to the stable public report contract."""
    return {output: row[source] for output, source in DEFINITIONS[report_type].fields.items()}


def report_summary(queryset, report_type):
    fields = DEFINITIONS[report_type].summary_fields
    if not fields:
        return {}
    values = queryset.aggregate(**{f"total_{field}": Sum(field) for field in fields})
    return {
        key: None if value is None else format(value, "f") if isinstance(value, Decimal) else value
        for key, value in values.items()
    }
