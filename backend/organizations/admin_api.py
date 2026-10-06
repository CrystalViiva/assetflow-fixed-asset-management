"""Tenant-admin APIs for organization reference data."""

from django.db import transaction
from django.db.models import Q
from rest_framework import serializers
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated

from audit.services import record_event
from common.pagination import StandardResultsPagination
from organizations.models import Department, Location


class OrganizationAdminPermission(IsAuthenticated):
    """Only an active tenant ADMIN may administer organization data."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        user = request.user
        return bool(
            user.is_active
            and user.organization_id
            and user.role == "ADMIN"
            and not user.is_superuser
        )


class StrictSerializer(serializers.ModelSerializer):
    def to_internal_value(self, data):
        if isinstance(data, dict):
            writable = {name for name, field in self.fields.items() if not field.read_only}
            unknown = set(data) - writable
            if unknown:
                raise serializers.ValidationError(
                    {key: "This field is not supported." for key in sorted(unknown)}
                )
        return super().to_internal_value(data)


class DepartmentAdminSerializer(StrictSerializer):
    organization_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = Department
        fields = ("id", "organization_id", "name", "code", "is_active", "created_at", "updated_at")
        read_only_fields = ("id", "organization_id", "created_at", "updated_at")


class LocationAdminSerializer(StrictSerializer):
    organization_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = Location
        fields = (
            "id",
            "organization_id",
            "name",
            "code",
            "address",
            "city",
            "state",
            "country",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "organization_id", "created_at", "updated_at")


class ScopedListCreateView(ListCreateAPIView):
    permission_classes = (OrganizationAdminPermission,)
    pagination_class = StandardResultsPagination
    model = None
    serializer_class = None
    entity_type = ""

    def get_queryset(self):
        queryset = self.model.objects.filter(organization_id=self.request.user.organization_id)
        search = self.request.query_params.get("search", "").strip()
        if len(search) > 200:
            raise serializers.ValidationError({"search": "Keep search to 200 characters or fewer."})
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(code__icontains=search))
        active = self.request.query_params.get("is_active")
        if active in {"true", "false"}:
            queryset = queryset.filter(is_active=active == "true")
        return queryset.order_by("name", "id")

    @transaction.atomic
    def perform_create(self, serializer):
        instance = serializer.save(organization=self.request.user.organization)
        record_event(
            organization=self.request.user.organization,
            user=self.request.user,
            action=f"{self.entity_type}_CREATED",
            entity_type=self.entity_type,
            entity_id=instance.id,
            ip_address=self.request.META.get("REMOTE_ADDR"),
            changes={
                "name": {"old": None, "new": instance.name},
                "code": {"old": None, "new": instance.code},
            },
        )


class ScopedDetailView(RetrieveUpdateAPIView):
    permission_classes = (OrganizationAdminPermission,)
    lookup_field = "id"
    model = None
    serializer_class = None
    entity_type = ""
    http_method_names = ("get", "put", "patch", "head", "options")

    def get_queryset(self):
        return self.model.objects.filter(organization_id=self.request.user.organization_id)

    @transaction.atomic
    def perform_update(self, serializer):
        instance = self.model.objects.select_for_update().get(
            pk=serializer.instance.pk,
            organization_id=self.request.user.organization_id,
        )
        serializer.instance = instance
        before = {field: getattr(instance, field) for field in serializer.validated_data}
        instance = serializer.save()
        changes = {
            field: {"old": before[field], "new": getattr(instance, field)}
            for field in before
            if before[field] != getattr(instance, field)
        }
        if changes:
            record_event(
                organization=self.request.user.organization,
                user=self.request.user,
                action=f"{self.entity_type}_UPDATED",
                entity_type=self.entity_type,
                entity_id=instance.id,
                ip_address=self.request.META.get("REMOTE_ADDR"),
                changes=changes,
            )


class DepartmentAdminList(ScopedListCreateView):
    model = Department
    serializer_class = DepartmentAdminSerializer
    entity_type = "DEPARTMENT"


class DepartmentAdminDetail(ScopedDetailView):
    model = Department
    serializer_class = DepartmentAdminSerializer
    entity_type = "DEPARTMENT"


class LocationAdminList(ScopedListCreateView):
    model = Location
    serializer_class = LocationAdminSerializer
    entity_type = "LOCATION"


class LocationAdminDetail(ScopedDetailView):
    model = Location
    serializer_class = LocationAdminSerializer
    entity_type = "LOCATION"
