"""Read-only tenant-scoped choices for the existing asset placement contract.

AssetSerializer accepts department/location UUIDs, but previously provided no way
for a browser client to discover them. No organization write API is introduced.
"""

from rest_framework import serializers
from rest_framework.generics import ListAPIView

from assets.permissions import AssetDomainPermission
from organizations.models import Department, Location


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
