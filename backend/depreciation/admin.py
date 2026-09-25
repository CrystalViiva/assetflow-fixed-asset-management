from django.contrib import admin

from depreciation.models import AccountingPeriod, DepreciationEntry, DepreciationSchedule


class LedgerRecordAdmin(admin.ModelAdmin):
    """Display accounting records without exposing direct mutation shortcuts."""

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        return queryset.filter(organization_id=request.user.organization_id)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_staff


@admin.register(AccountingPeriod)
class AccountingPeriodAdmin(LedgerRecordAdmin):
    list_display = (
        "organization",
        "year",
        "month",
        "status",
        "opened_at",
        "closed_at",
        "closed_by",
    )
    list_filter = ("organization", "status", "year")
    search_fields = ("organization__name", "organization__code")
    ordering = ("-year", "-month")


@admin.register(DepreciationSchedule)
class DepreciationScheduleAdmin(LedgerRecordAdmin):
    list_display = (
        "asset",
        "organization",
        "method",
        "capitalized_cost",
        "depreciable_base",
        "residual_value",
        "useful_life_months",
        "periodic_depreciation",
        "status",
    )
    list_filter = ("organization", "method", "status")
    search_fields = ("asset__asset_tag", "asset__name")
    ordering = ("asset__asset_tag",)


@admin.register(DepreciationEntry)
class DepreciationEntryAdmin(LedgerRecordAdmin):
    list_display = (
        "asset",
        "organization",
        "accounting_period",
        "opening_book_value",
        "depreciation_amount",
        "accumulated_depreciation",
        "closing_book_value",
        "posted_at",
    )
    list_filter = ("organization", "accounting_period__year", "accounting_period__month")
    search_fields = ("asset__asset_tag", "asset__name")
    ordering = ("-accounting_period__year", "-accounting_period__month", "asset__asset_tag")
