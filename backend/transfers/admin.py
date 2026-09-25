from django.contrib import admin

from transfers.models import AssetAssignment, AssetTransfer


class OrganizationScopedHistoryAdmin(admin.ModelAdmin):
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


@admin.register(AssetAssignment)
class AssetAssignmentAdmin(OrganizationScopedHistoryAdmin):
    list_display = (
        "asset",
        "organization",
        "assigned_to",
        "department",
        "location",
        "assigned_at",
        "returned_at",
    )
    list_filter = ("organization", "department", "location", "returned_at")
    search_fields = ("asset__asset_tag", "asset__name", "assigned_to__email", "notes")
    ordering = ("-assigned_at",)


@admin.register(AssetTransfer)
class AssetTransferAdmin(OrganizationScopedHistoryAdmin):
    list_display = (
        "asset",
        "organization",
        "status",
        "from_department",
        "to_department",
        "requested_by",
        "requested_at",
        "completed_at",
    )
    list_filter = ("organization", "status", "from_department", "to_department", "requested_at")
    search_fields = ("asset__asset_tag", "asset__name", "reason", "requested_by__email")
    ordering = ("-requested_at",)
