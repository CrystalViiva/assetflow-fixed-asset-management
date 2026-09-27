from django.contrib import admin

from assurance.models import AssuranceFinding, AssuranceFindingOccurrence, AssuranceRun


class OrganizationScopedAssuranceAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        if not request.user.organization_id:
            return queryset.none()
        return queryset.filter(organization_id=request.user.organization_id)

    def get_list_filter(self, request):
        filters = super().get_list_filter(request)
        if request.user.is_superuser:
            return filters
        return tuple(field for field in filters if field != "organization")


@admin.register(AssuranceRun)
class AssuranceRunAdmin(OrganizationScopedAssuranceAdmin):
    list_display = (
        "created_at",
        "organization",
        "run_type",
        "status",
        "assets_evaluated",
        "findings_generated",
        "started_by",
    )
    list_filter = ("organization", "run_type", "status")
    search_fields = ("id", "organization__name", "started_by__email")
    readonly_fields = tuple(field.name for field in AssuranceRun._meta.fields)
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class AssuranceFindingOccurrenceInline(admin.TabularInline):
    model = AssuranceFindingOccurrence
    extra = 0
    can_delete = False
    readonly_fields = tuple(field.name for field in AssuranceFindingOccurrence._meta.fields)

    def has_add_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        if not request.user.organization_id:
            return queryset.none()
        return queryset.filter(organization_id=request.user.organization_id)


@admin.register(AssuranceFinding)
class AssuranceFindingAdmin(OrganizationScopedAssuranceAdmin):
    list_display = (
        "first_detected_at",
        "organization",
        "asset",
        "finding_type",
        "severity",
        "status",
        "occurrence_count",
    )
    list_filter = ("organization", "finding_type", "severity", "status", "source")
    search_fields = ("asset__asset_tag", "description", "expected_value", "observed_value")
    readonly_fields = tuple(field.name for field in AssuranceFinding._meta.fields)
    inlines = (AssuranceFindingOccurrenceInline,)
    ordering = ("-last_detected_at",)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
