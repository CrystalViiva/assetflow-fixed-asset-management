from django.contrib import admin

from maintenance.models import MaintenanceCost, MaintenancePlan, MaintenanceRecord, WorkOrder


class OrganizationScopedReadOnlyAdmin(admin.ModelAdmin):
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


@admin.register(MaintenancePlan)
class MaintenancePlanAdmin(OrganizationScopedReadOnlyAdmin):
    list_display = (
        "asset",
        "organization",
        "maintenance_type",
        "frequency_value",
        "frequency_unit",
        "next_due_date",
        "active",
    )
    list_filter = ("organization", "maintenance_type", "active", "frequency_unit")
    search_fields = ("asset__asset_tag", "asset__name", "instructions")
    readonly_fields = ("created_at", "updated_at", "created_by")


@admin.register(WorkOrder)
class WorkOrderAdmin(OrganizationScopedReadOnlyAdmin):
    list_display = (
        "work_order_number",
        "asset",
        "organization",
        "maintenance_type",
        "priority",
        "status",
        "assigned_to",
        "opened_at",
        "due_date",
    )
    list_filter = ("organization", "maintenance_type", "priority", "status", "opened_at")
    search_fields = (
        "work_order_number",
        "asset__asset_tag",
        "asset__name",
        "description",
        "diagnosis",
    )
    readonly_fields = tuple(field.name for field in WorkOrder._meta.fields)


@admin.register(MaintenanceCost)
class MaintenanceCostAdmin(OrganizationScopedReadOnlyAdmin):
    list_display = (
        "work_order",
        "organization",
        "cost_type",
        "description",
        "quantity",
        "unit_cost",
        "total_cost",
        "incurred_at",
    )
    list_filter = ("organization", "cost_type", "incurred_at")
    search_fields = (
        "work_order__work_order_number",
        "work_order__asset__asset_tag",
        "description",
        "vendor_reference",
    )
    readonly_fields = tuple(field.name for field in MaintenanceCost._meta.fields)


@admin.register(MaintenanceRecord)
class MaintenanceRecordAdmin(OrganizationScopedReadOnlyAdmin):
    list_display = (
        "asset",
        "work_order",
        "organization",
        "maintenance_date",
        "maintenance_type",
        "total_cost",
        "downtime_minutes",
    )
    list_filter = ("organization", "maintenance_type", "maintenance_date")
    search_fields = ("asset__asset_tag", "work_order__work_order_number", "summary")
    readonly_fields = tuple(field.name for field in MaintenanceRecord._meta.fields)
