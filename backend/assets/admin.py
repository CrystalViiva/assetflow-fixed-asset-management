from datetime import date, datetime
from decimal import Decimal

from django.contrib import admin
from django.db import transaction

from assets.models import Acquisition, Asset, AssetCategory, AssetStatus
from assets.services import create_acquisition, update_acquisition
from assets.services.acquisition import ACQUISITION_FIELDS
from audit.services import record_event


def _audit_value(value):
    if hasattr(value, "_meta"):
        return str(value.pk)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


class OrganizationScopedAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        return queryset.filter(organization_id=request.user.organization_id)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if not request.user.is_superuser:
            organization_id = request.user.organization_id
            if db_field.name == "organization":
                kwargs["queryset"] = db_field.remote_field.model.objects.filter(pk=organization_id)
            elif db_field.name in {"asset", "category", "department", "location"}:
                kwargs["queryset"] = db_field.remote_field.model.objects.filter(
                    organization_id=organization_id
                )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(AssetCategory)
class AssetCategoryAdmin(OrganizationScopedAdmin):
    list_display = (
        "name",
        "code",
        "organization",
        "default_useful_life_months",
        "default_depreciation_method",
        "is_active",
    )
    list_filter = ("organization", "is_active", "default_depreciation_method")
    search_fields = ("name", "code", "organization__name")
    readonly_fields = ("created_at", "updated_at")

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            obj.organization = request.user.organization
        super().save_model(request, obj, form, change)


@admin.register(Asset)
class AssetAdmin(OrganizationScopedAdmin):
    accounting_fields = (
        "acquisition_date",
        "capitalization_date",
        "available_for_use_date",
        "purchase_cost",
        "residual_value",
        "useful_life_months",
        "depreciation_method",
    )
    list_display = (
        "asset_tag",
        "name",
        "organization",
        "category",
        "department",
        "location",
        "status",
        "condition",
        "purchase_cost",
        "current_book_value",
    )
    list_filter = (
        "organization",
        "status",
        "condition",
        "category",
        "department",
        "location",
        "depreciation_method",
    )
    search_fields = (
        "asset_tag",
        "name",
        "serial_number",
        "model_number",
        "manufacturer",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
        "accumulated_depreciation",
        "current_book_value",
        "status",
    )
    fieldsets = (
        ("Identification", {"fields": ("asset_tag", "name", "description", "category")}),
        (
            "Organization and location",
            {"fields": ("organization", "department", "location", "status")},
        ),
        (
            "Asset details",
            {"fields": ("serial_number", "model_number", "manufacturer", "condition")},
        ),
        (
            "Accounting policy and balances",
            {
                "fields": (
                    "acquisition_date",
                    "capitalization_date",
                    "available_for_use_date",
                    "purchase_cost",
                    "residual_value",
                    "useful_life_months",
                    "depreciation_method",
                    "accumulated_depreciation",
                    "current_book_value",
                )
            },
        ),
        ("Record history", {"fields": ("created_at", "updated_at", "created_by", "updated_by")}),
    )

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            obj.organization = request.user.organization
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        obj.full_clean()
        with transaction.atomic():
            super().save_model(request, obj, form, change)
            if change:
                changes = {
                    field_name: {
                        "from": _audit_value(form.initial.get(field_name)),
                        "to": _audit_value(form.cleaned_data.get(field_name)),
                    }
                    for field_name in form.changed_data
                }
                if not changes:
                    return
                action = "ASSET_UPDATED"
            else:
                changes = {
                    "asset_tag": {"from": None, "to": obj.asset_tag},
                    "name": {"from": None, "to": obj.name},
                    "status": {"from": None, "to": obj.status},
                }
                action = "ASSET_CREATED"

            record_event(
                organization=obj.organization,
                user=request.user,
                action=action,
                entity_type="ASSET",
                entity_id=obj.pk,
                ip_address=request.META.get("REMOTE_ADDR"),
                changes=changes,
                metadata={"source": "django_admin"},
            )

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        if obj and obj.status not in (AssetStatus.DRAFT, AssetStatus.PENDING_CAPITALIZATION):
            return (*fields, *self.accounting_fields)
        return fields

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Acquisition)
class AcquisitionAdmin(OrganizationScopedAdmin):
    list_display = (
        "invoice_number",
        "asset",
        "vendor_name",
        "organization",
        "acquisition_date",
        "capitalization_date",
        "currency",
        "total_cost",
        "status",
    )
    list_filter = ("organization", "status", "currency", "acquisition_date")
    search_fields = (
        "invoice_number",
        "reference",
        "vendor_name",
        "asset__asset_tag",
        "asset__name",
    )
    readonly_fields = (
        "organization",
        "total_cost",
        "status",
        "created_by",
        "updated_by",
        "created_at",
        "updated_at",
    )
    fieldsets = (
        (
            "Asset and source documents",
            {"fields": ("organization", "asset", "vendor_name", "invoice_number", "reference")},
        ),
        ("Dates and currency", {"fields": ("acquisition_date", "capitalization_date", "currency")}),
        (
            "Capitalizable cost components",
            {
                "fields": (
                    "purchase_price",
                    "freight_cost",
                    "installation_cost",
                    "civil_works_cost",
                    "other_capitalizable_cost",
                    "total_cost",
                )
            },
        ),
        (
            "Notes and record history",
            {"fields": ("notes", "status", "created_by", "updated_by", "created_at", "updated_at")},
        ),
    )

    def save_model(self, request, obj, form, change):
        values = {field: getattr(obj, field) for field in ACQUISITION_FIELDS}
        if change:
            acquisition = update_acquisition(
                acquisition_id=obj.pk,
                actor=request.user,
                data=values,
                ip_address=request.META.get("REMOTE_ADDR"),
            )
        else:
            acquisition = create_acquisition(
                actor=request.user,
                data={"asset": obj.asset, **values},
                ip_address=request.META.get("REMOTE_ADDR"),
            )
        obj.__dict__.update(acquisition.__dict__)

    def has_delete_permission(self, request, obj=None):
        return False
