"""Organization-scoped live operational dashboard aggregates."""

from datetime import date
from decimal import Decimal

from django.db.models import CharField, Count, DecimalField, F, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Cast, Coalesce
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import UserRole
from assets.models import Acquisition, AcquisitionStatus, Asset, AssetStatus
from assurance.models import ACTIVE_FINDING_STATUSES, AssuranceFinding
from audit.models import AuditLog
from depreciation.models import DepreciationEntry
from disposals.models import Disposal, DisposalStatus
from maintenance.models import MaintenanceCost, WorkOrder, WorkOrderStatus
from transfers.models import AssetTransfer, TransferStatus
from verification.models import ExceptionStatus, VerificationException

DASHBOARD_ROLES = {
    UserRole.ADMIN,
    UserRole.ASSET_MANAGER,
    UserRole.ACCOUNTANT,
    UserRole.DEPARTMENT_MANAGER,
}
CONTROLLED_STATUSES = (
    AssetStatus.ACTIVE,
    AssetStatus.IN_MAINTENANCE,
    AssetStatus.TRANSFERRED,
    AssetStatus.IMPAIRED,
)


class DashboardGroupSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    count = serializers.IntegerField(min_value=0)
    book_value = serializers.DecimalField(max_digits=24, decimal_places=2, required=False)


class DashboardSeriesSerializer(serializers.Serializer):
    period = serializers.RegexField(r"^\d{4}-(0[1-9]|1[0-2])$")
    amount = serializers.DecimalField(max_digits=24, decimal_places=2)


class DashboardActivitySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    timestamp = serializers.DateTimeField()
    actor = serializers.EmailField(allow_null=True)
    action = serializers.CharField()
    entity_type = serializers.CharField()
    entity_id = serializers.CharField()


class DashboardPortfolioSerializer(serializers.Serializer):
    registered_assets = serializers.IntegerField(min_value=0)
    currently_held_assets = serializers.IntegerField(min_value=0)
    capitalized_assets = serializers.IntegerField(min_value=0)
    disposed_assets = serializers.IntegerField(min_value=0)


class DashboardFinancialSerializer(serializers.Serializer):
    capitalized_cost = serializers.DecimalField(max_digits=24, decimal_places=2)
    book_value = serializers.DecimalField(max_digits=24, decimal_places=2)
    accumulated_depreciation = serializers.DecimalField(max_digits=24, decimal_places=2)
    current_month_posted_depreciation = serializers.DecimalField(max_digits=24, decimal_places=2)
    current_month_capitalized_cost = serializers.DecimalField(max_digits=24, decimal_places=2)


class DashboardDistributionsSerializer(serializers.Serializer):
    status = DashboardGroupSerializer(many=True)
    category = DashboardGroupSerializer(many=True)
    department = DashboardGroupSerializer(many=True)
    location = DashboardGroupSerializer(many=True)


class DashboardTrendsSerializer(serializers.Serializer):
    posted_depreciation = DashboardSeriesSerializer(many=True)
    capitalizations = DashboardSeriesSerializer(many=True)


class DashboardOperationsSerializer(serializers.Serializer):
    open_work_orders = serializers.IntegerField(min_value=0)
    critical_open_work_orders = serializers.IntegerField(min_value=0)
    current_month_maintenance_cost = serializers.DecimalField(max_digits=24, decimal_places=2)
    requested_transfers = serializers.IntegerField(min_value=0)
    approved_transfers = serializers.IntegerField(min_value=0)
    pending_disposals = serializers.IntegerField(min_value=0)
    approved_disposals = serializers.IntegerField(min_value=0)


class DashboardControlsSerializer(serializers.Serializer):
    open_verification_exceptions = serializers.IntegerField(min_value=0)
    open_assurance_findings = serializers.IntegerField(min_value=0)


class DashboardMetricsSerializer(serializers.Serializer):
    as_of = serializers.DateTimeField()
    currency = serializers.CharField(min_length=3, max_length=3)
    scope = serializers.ChoiceField(choices=("organization", "department"))
    portfolio = DashboardPortfolioSerializer()
    financial = DashboardFinancialSerializer()
    distributions = DashboardDistributionsSerializer()
    trends = DashboardTrendsSerializer()
    operations = DashboardOperationsSerializer()
    controls = DashboardControlsSerializer()
    recent_activity = DashboardActivitySerializer(many=True)


class DashboardPermission(BasePermission):
    message = "Your role cannot access organization dashboard analytics."

    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated or not user.organization_id:
            return False
        if user.role not in DASHBOARD_ROLES and not user.is_superuser:
            return False
        if user.role == UserRole.DEPARTMENT_MANAGER and not user.department_id:
            return False
        return True


def _money(value):
    return format((value or Decimal("0.00")).quantize(Decimal("0.01")), ".2f")


def _period(year, month):
    return f"{year:04d}-{month:02d}"


class DashboardMetricsView(APIView):
    permission_classes = (IsAuthenticated, DashboardPermission)

    @extend_schema(
        responses=DashboardMetricsSerializer,
        description=("Live, bounded aggregates for the authenticated organization and role scope."),
    )
    def get(self, request):
        user = request.user
        organization = user.organization
        now = timezone.now()
        department_id = user.department_id if user.role == UserRole.DEPARTMENT_MANAGER else None
        assets = Asset.objects.filter(organization_id=user.organization_id)
        if department_id:
            assets = assets.filter(department_id=department_id)

        controlled = assets.filter(status__in=CONTROLLED_STATUSES)
        capitalized = controlled.filter(capitalization_date__isnull=False)
        latest_entries = DepreciationEntry.objects.filter(
            organization_id=user.organization_id, asset_id=OuterRef("pk")
        ).order_by(
            "-accounting_period__year",
            "-accounting_period__month",
            "-posted_at",
            "-id",
        )
        money_field = DecimalField(max_digits=24, decimal_places=2)
        ledger_book_value = Coalesce(
            Subquery(latest_entries.values("closing_book_value")[:1]),
            F("purchase_cost"),
            output_field=money_field,
        )
        ledger_accumulated_depreciation = Coalesce(
            Subquery(latest_entries.values("accumulated_depreciation")[:1]),
            Value(Decimal("0.00")),
            output_field=money_field,
        )
        capitalized_with_ledger = capitalized.annotate(
            ledger_book_value=ledger_book_value,
            ledger_accumulated_depreciation=ledger_accumulated_depreciation,
        )
        financial = capitalized_with_ledger.aggregate(
            cost=Sum("purchase_cost"),
            depreciation=Sum("ledger_accumulated_depreciation"),
            book_value=Sum("ledger_book_value"),
        )
        asset_counts = assets.aggregate(
            registered=Count("id"),
            disposed=Count("id", filter=Q(status=AssetStatus.DISPOSED)),
            controlled=Count("id", filter=Q(status__in=CONTROLLED_STATUSES)),
            capitalized=Count(
                "id", filter=Q(status__in=CONTROLLED_STATUSES, capitalization_date__isnull=False)
            ),
        )

        operations = WorkOrder.objects.filter(organization_id=user.organization_id)
        transfers = AssetTransfer.objects.filter(organization_id=user.organization_id)
        disposals = Disposal.objects.filter(organization_id=user.organization_id)
        exceptions = VerificationException.objects.filter(organization_id=user.organization_id)
        findings = AssuranceFinding.objects.filter(
            organization_id=user.organization_id, status__in=ACTIVE_FINDING_STATUSES
        )
        costs = MaintenanceCost.objects.filter(organization_id=user.organization_id)
        depreciation = DepreciationEntry.objects.filter(organization_id=user.organization_id)
        acquisitions = Acquisition.objects.filter(
            organization_id=user.organization_id,
            status=AcquisitionStatus.CAPITALIZED,
            capitalization_date__isnull=False,
        )
        if department_id:
            operations = operations.filter(asset__department_id=department_id)
            transfers = transfers.filter(asset__department_id=department_id)
            disposals = disposals.filter(asset__department_id=department_id)
            exceptions = exceptions.filter(asset__department_id=department_id)
            findings = findings.filter(asset__department_id=department_id)
            costs = costs.filter(work_order__asset__department_id=department_id)
            depreciation = depreciation.filter(asset__department_id=department_id)
            acquisitions = acquisitions.filter(asset__department_id=department_id)

        open_work = operations.filter(
            status__in=(WorkOrderStatus.OPEN, WorkOrderStatus.ASSIGNED, WorkOrderStatus.IN_PROGRESS)
        )
        recent_events = AuditLog.objects.filter(organization_id=user.organization_id)
        if department_id:
            visible_asset_ids = assets.annotate(
                id_text=Cast("id", output_field=CharField())
            ).values("id_text")
            recent_events = recent_events.filter(
                entity_type="ASSET", entity_id__in=visible_asset_ids
            )
        recent_events = recent_events.select_related("user").order_by("-timestamp")[:8]

        month_start = date(now.year, now.month, 1)
        month_end = date(now.year + (now.month == 12), now.month % 12 + 1, 1)
        month_costs = costs.filter(
            incurred_at__date__gte=month_start, incurred_at__date__lt=month_end
        ).aggregate(total=Sum("total_cost"))["total"]
        month_depreciation = depreciation.filter(
            accounting_period__year=now.year, accounting_period__month=now.month
        ).aggregate(total=Sum("depreciation_amount"))["total"]
        month_capex = acquisitions.filter(
            capitalization_date__year=now.year, capitalization_date__month=now.month
        ).aggregate(total=Sum("total_cost"))["total"]

        status_groups = [
            {
                "key": row["status"],
                "label": row["status"].replace("_", " ").title(),
                "count": row["count"],
            }
            for row in assets.values("status").annotate(count=Count("id")).order_by("status")
        ]
        category_groups = [
            {
                "key": str(row["category_id"]),
                "label": row["category__name"],
                "count": row["count"],
                "book_value": _money(row["book_value"]),
            }
            for row in capitalized_with_ledger.values("category_id", "category__name")
            .annotate(count=Count("id"), book_value=Sum("ledger_book_value"))
            .order_by("category__name", "category_id")
        ]
        department_groups = [
            {
                "key": str(row["department_id"] or "UNASSIGNED"),
                "label": row["department__name"] or "Unassigned",
                "count": row["count"],
                "book_value": _money(row["book_value"]),
            }
            for row in capitalized_with_ledger.values("department_id", "department__name")
            .annotate(count=Count("id"), book_value=Sum("ledger_book_value"))
            .order_by("department__name", "department_id")
        ]
        location_groups = [
            {
                "key": str(row["location_id"] or "UNASSIGNED"),
                "label": row["location__name"] or "Unassigned",
                "count": row["count"],
                "book_value": _money(row["book_value"]),
            }
            for row in capitalized_with_ledger.values("location_id", "location__name")
            .annotate(count=Count("id"), book_value=Sum("ledger_book_value"))
            .order_by("location__name", "location_id")
        ]
        start_year = now.year - (1 if now.month <= 11 else 0)
        start_month = now.month - 11 if now.month > 11 else now.month + 1
        start_period = Q(accounting_period__year__gt=start_year) | Q(
            accounting_period__year=start_year, accounting_period__month__gte=start_month
        )
        end_period = Q(accounting_period__year__lt=now.year) | Q(
            accounting_period__year=now.year, accounting_period__month__lte=now.month
        )
        posted = (
            depreciation.filter(start_period & end_period)
            .values("accounting_period__year", "accounting_period__month")
            .annotate(amount=Sum("depreciation_amount"))
            .order_by("accounting_period__year", "accounting_period__month")
        )
        depreciation_series = [
            {
                "period": _period(row["accounting_period__year"], row["accounting_period__month"]),
                "amount": _money(row["amount"]),
            }
            for row in posted
        ]
        capex_start = date(start_year, start_month, 1)
        capex_rows = (
            acquisitions.filter(
                capitalization_date__gte=capex_start, capitalization_date__lte=now.date()
            )
            .values("capitalization_date__year", "capitalization_date__month")
            .annotate(amount=Sum("total_cost"))
            .order_by("capitalization_date__year", "capitalization_date__month")
        )
        capex_series = [
            {
                "period": _period(
                    row["capitalization_date__year"], row["capitalization_date__month"]
                ),
                "amount": _money(row["amount"]),
            }
            for row in capex_rows
        ]

        return Response(
            {
                "as_of": now.isoformat(),
                "currency": organization.currency,
                "scope": "department" if department_id else "organization",
                "portfolio": {
                    "registered_assets": asset_counts["registered"],
                    "currently_held_assets": asset_counts["controlled"],
                    "capitalized_assets": asset_counts["capitalized"],
                    "disposed_assets": asset_counts["disposed"],
                },
                "financial": {
                    "capitalized_cost": _money(financial["cost"]),
                    "book_value": _money(financial["book_value"]),
                    "accumulated_depreciation": _money(financial["depreciation"]),
                    "current_month_posted_depreciation": _money(month_depreciation),
                    "current_month_capitalized_cost": _money(month_capex),
                },
                "distributions": {
                    "status": status_groups,
                    "category": category_groups,
                    "department": department_groups,
                    "location": location_groups,
                },
                "trends": {
                    "posted_depreciation": depreciation_series,
                    "capitalizations": capex_series,
                },
                "operations": {
                    "open_work_orders": open_work.count(),
                    "critical_open_work_orders": open_work.filter(priority="CRITICAL").count(),
                    "current_month_maintenance_cost": _money(month_costs),
                    "requested_transfers": transfers.filter(
                        status=TransferStatus.REQUESTED
                    ).count(),
                    "approved_transfers": transfers.filter(status=TransferStatus.APPROVED).count(),
                    "pending_disposals": disposals.filter(
                        status=DisposalStatus.PENDING_APPROVAL
                    ).count(),
                    "approved_disposals": disposals.filter(status=DisposalStatus.APPROVED).count(),
                },
                "controls": {
                    "open_verification_exceptions": exceptions.filter(
                        status__in=(ExceptionStatus.OPEN, ExceptionStatus.UNDER_REVIEW)
                    ).count(),
                    "open_assurance_findings": findings.count(),
                },
                "recent_activity": [
                    {
                        "id": str(row.id),
                        "timestamp": row.timestamp.isoformat(),
                        "actor": (
                            row.user.email
                            if row.user_id and row.user.organization_id == user.organization_id
                            else None
                        ),
                        "action": row.action,
                        "entity_type": row.entity_type,
                        "entity_id": row.entity_id,
                    }
                    for row in recent_events
                ],
            }
        )
