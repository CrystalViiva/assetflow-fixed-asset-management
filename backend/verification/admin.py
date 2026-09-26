from django.contrib import admin

from verification.models import (
    PhysicalVerification,
    VerificationCampaign,
    VerificationEvidence,
    VerificationException,
)


@admin.register(VerificationCampaign)
class VerificationCampaignAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "scope_type", "status", "start_date", "due_date")
    list_filter = ("organization", "scope_type", "status")
    search_fields = ("name", "description", "department__name", "location__name")
    readonly_fields = tuple(field.name for field in VerificationCampaign._meta.fields)

    def get_queryset(self, request):
        queryset = (
            super().get_queryset(request).select_related("organization", "department", "location")
        )
        return (
            queryset
            if request.user.is_superuser
            else queryset.filter(organization_id=request.user.organization_id)
        )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PhysicalVerification)
class PhysicalVerificationAdmin(admin.ModelAdmin):
    list_display = (
        "campaign",
        "asset",
        "observed_asset_tag",
        "result",
        "observed_condition",
        "verified_at",
        "verified_by",
    )
    list_filter = ("organization", "campaign", "result", "observed_condition", "verified_at")
    search_fields = (
        "observed_asset_tag",
        "asset__asset_tag",
        "asset__name",
        "observed_description",
        "notes",
    )
    readonly_fields = tuple(field.name for field in PhysicalVerification._meta.fields)

    def get_queryset(self, request):
        queryset = (
            super()
            .get_queryset(request)
            .select_related("organization", "campaign", "asset", "verified_by")
        )
        return (
            queryset
            if request.user.is_superuser
            else queryset.filter(organization_id=request.user.organization_id)
        )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(VerificationException)
class VerificationExceptionAdmin(admin.ModelAdmin):
    list_display = (
        "exception_type",
        "severity",
        "status",
        "campaign",
        "asset",
        "assigned_to",
        "created_at",
    )
    list_filter = ("organization", "exception_type", "severity", "status", "created_at")
    search_fields = ("description", "asset__asset_tag", "resolution_notes", "resolution_reference")
    readonly_fields = tuple(field.name for field in VerificationException._meta.fields)

    def get_queryset(self, request):
        queryset = (
            super()
            .get_queryset(request)
            .select_related(
                "organization", "campaign", "verification", "asset", "assigned_to", "resolved_by"
            )
        )
        return (
            queryset
            if request.user.is_superuser
            else queryset.filter(organization_id=request.user.organization_id)
        )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(VerificationEvidence)
class VerificationEvidenceAdmin(admin.ModelAdmin):
    list_display = (
        "evidence_type",
        "verification",
        "exception",
        "file_name",
        "captured_at",
        "captured_by",
    )
    list_filter = ("organization", "evidence_type", "captured_at")
    search_fields = ("file_name", "storage_key", "external_reference", "description")
    readonly_fields = tuple(field.name for field in VerificationEvidence._meta.fields)

    def get_queryset(self, request):
        queryset = (
            super()
            .get_queryset(request)
            .select_related("organization", "verification", "exception", "captured_by")
        )
        return (
            queryset
            if request.user.is_superuser
            else queryset.filter(organization_id=request.user.organization_id)
        )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
