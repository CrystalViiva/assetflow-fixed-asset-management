from django.contrib import admin

from disposals.models import Disposal


@admin.register(Disposal)
class DisposalAdmin(admin.ModelAdmin):
    list_display = (
        "asset",
        "organization",
        "disposal_date",
        "disposal_method",
        "status",
        "proceeds",
        "carrying_amount",
        "gain_or_loss",
        "requested_by",
        "approved_by",
    )
    list_filter = ("organization", "status", "disposal_method", "disposal_date")
    search_fields = ("asset__asset_tag", "asset__name", "reason", "requested_by__email")
    readonly_fields = tuple(field.name for field in Disposal._meta.fields)

    def get_queryset(self, request):
        queryset = (
            super()
            .get_queryset(request)
            .select_related("organization", "asset", "requested_by", "approved_by")
        )
        if request.user.is_superuser:
            return queryset
        return queryset.filter(organization_id=request.user.organization_id)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
