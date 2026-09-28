from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from accounts.models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ("email",)
    list_display = ("email", "organization", "department", "role", "is_active", "is_staff")
    list_filter = ("role", "is_active", "is_staff", "organization", "department")
    search_fields = ("email",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Organization", {"fields": ("organization", "department", "role")}),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Timestamps", {"fields": ("last_login", "created_at", "updated_at")}),
    )
    readonly_fields = ("created_at", "updated_at")

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
        return tuple(field for field in filters if field not in {"organization", "department"})

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if request.user.is_superuser:
            return fieldsets
        scoped = []
        for title, options in fieldsets:
            fields = tuple(
                field
                for field in options.get("fields", ())
                if field not in {"is_staff", "is_superuser", "groups", "user_permissions"}
            )
            if fields:
                scoped.append((title, {**options, "fields": fields}))
        return tuple(scoped)

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        if request.user.is_superuser:
            return fields
        return (*fields, "organization")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if not request.user.is_superuser and request.user.organization_id:
            if db_field.name == "organization":
                kwargs["queryset"] = db_field.remote_field.model.objects.filter(
                    pk=request.user.organization_id
                )
            elif db_field.name == "department":
                kwargs["queryset"] = db_field.remote_field.model.objects.filter(
                    organization_id=request.user.organization_id
                )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            obj.organization = request.user.organization
            if change:
                original = self.get_queryset(request).get(pk=obj.pk)
                obj.is_staff = original.is_staff
                obj.is_superuser = original.is_superuser
        obj.full_clean()
        super().save_model(request, obj, form, change)

    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "password1", "password2", "role")}),
    )
