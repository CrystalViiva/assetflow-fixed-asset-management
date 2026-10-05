"""Read-only tenant-scoped choices for the existing asset placement contract.

AssetSerializer accepts department/location UUIDs, but previously provided no way
for a browser client to discover them. No organization write API is introduced.
"""

from rest_framework import serializers
from rest_framework.generics import ListAPIView
from rest_framework.permissions import SAFE_METHODS, BasePermission

from accounts.models import User, UserRole
from assets.permissions import AssetDomainPermission
from organizations.models import Department, Location


class CustodianReferencePermission(BasePermission):
    """Only asset managers can discover tenant users for custody assignment."""

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user.is_authenticated
            and user.organization_id
            and request.method in SAFE_METHODS
            and (user.is_superuser or user.role in {UserRole.ADMIN, UserRole.ASSET_MANAGER})
        )


class CustodianReferenceSerializer(serializers.ModelSerializer):
    department_id = serializers.UUIDField(read_only=True, allow_null=True)
    department_name = serializers.CharField(
        source="department.name", read_only=True, allow_null=True
    )

    class Meta:
        model = User
        fields = ("id", "email", "role", "department_id", "department_name")
        read_only_fields = fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # User.department is a normal FK, so legacy or direct ORM writes can
        # leave a cross-organization relation even though the user is scoped.
        if (
            instance.department_id
            and instance.department.organization_id != instance.organization_id
        ):
            data["department_id"] = None
            data["department_name"] = None
        return data


class CustodianReferenceList(ListAPIView):
    serializer_class = CustodianReferenceSerializer
    permission_classes = (CustodianReferencePermission,)

    def get_queryset(self):
        return (
            User.objects.filter(
                organization_id=getattr(self.request.user, "organization_id", None), is_active=True
            )
            .select_related("department")
            .order_by("email", "id")
        )


class DepartmentReferenceSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = Department
        fields = ("id", "organization_id", "name", "code", "is_active")
        read_only_fields = fields


class LocationReferenceSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = Location
        fields = ("id", "organization_id", "name", "code", "is_active")
        read_only_fields = fields


class DepartmentReferenceList(ListAPIView):
    serializer_class = DepartmentReferenceSerializer
    permission_classes = (AssetDomainPermission,)

    def get_queryset(self):
        return Department.objects.filter(
            organization_id=getattr(self.request.user, "organization_id", None)
        ).order_by("name", "id")


class LocationReferenceList(ListAPIView):
    serializer_class = LocationReferenceSerializer
    permission_classes = (AssetDomainPermission,)

    def get_queryset(self):
        return Location.objects.filter(
            organization_id=getattr(self.request.user, "organization_id", None)
        ).order_by("name", "id")
