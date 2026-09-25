from rest_framework import serializers

from accounts.models import User
from assets.models import Asset
from organizations.models import Department, Location
from transfers.models import AssetAssignment, AssetTransfer


class AssetAssignmentSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    asset_id = serializers.PrimaryKeyRelatedField(source="asset", queryset=Asset.objects.none())
    asset_tag = serializers.CharField(source="asset.asset_tag", read_only=True)
    asset_name = serializers.CharField(source="asset.name", read_only=True)
    assigned_to_id = serializers.PrimaryKeyRelatedField(
        source="assigned_to", queryset=User.objects.none(), required=False, allow_null=True
    )
    assigned_to_email = serializers.EmailField(
        source="assigned_to.email", read_only=True, allow_null=True
    )
    department_id = serializers.PrimaryKeyRelatedField(
        source="department", queryset=Department.objects.none(), required=False, allow_null=True
    )
    department_name = serializers.CharField(
        source="department.name", read_only=True, allow_null=True
    )
    location_id = serializers.PrimaryKeyRelatedField(
        source="location", queryset=Location.objects.none(), required=False, allow_null=True
    )
    location_name = serializers.CharField(source="location.name", read_only=True, allow_null=True)
    returned_by_email = serializers.EmailField(
        source="returned_by.email", read_only=True, allow_null=True
    )
    created_by_email = serializers.EmailField(source="created_by.email", read_only=True)

    class Meta:
        model = AssetAssignment
        fields = (
            "id",
            "organization_id",
            "asset_id",
            "asset_tag",
            "asset_name",
            "assigned_to_id",
            "assigned_to_email",
            "department_id",
            "department_name",
            "location_id",
            "location_name",
            "assigned_at",
            "returned_at",
            "returned_by_email",
            "notes",
            "created_by_email",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "organization_id",
            "asset_tag",
            "asset_name",
            "assigned_to_email",
            "department_name",
            "location_name",
            "returned_at",
            "returned_by_email",
            "created_by_email",
            "created_at",
            "updated_at",
        )
        validators = ()

    def get_fields(self):
        fields = super().get_fields()
        user = getattr(self.context.get("request"), "user", None)
        organization_id = getattr(user, "organization_id", None)
        fields["asset_id"].queryset = Asset.objects.filter(organization_id=organization_id)
        fields["assigned_to_id"].queryset = User.objects.filter(organization_id=organization_id)
        fields["department_id"].queryset = Department.objects.filter(
            organization_id=organization_id
        )
        fields["location_id"].queryset = Location.objects.filter(organization_id=organization_id)
        return fields


class AssetTransferSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    asset_id = serializers.PrimaryKeyRelatedField(source="asset", queryset=Asset.objects.none())
    asset_tag = serializers.CharField(source="asset.asset_tag", read_only=True)
    asset_name = serializers.CharField(source="asset.name", read_only=True)
    from_department_id = serializers.UUIDField(read_only=True, allow_null=True)
    from_department_name = serializers.CharField(
        source="from_department.name", read_only=True, allow_null=True
    )
    from_location_id = serializers.UUIDField(read_only=True, allow_null=True)
    from_location_name = serializers.CharField(
        source="from_location.name", read_only=True, allow_null=True
    )
    to_department_id = serializers.PrimaryKeyRelatedField(
        source="to_department", queryset=Department.objects.none(), allow_null=True
    )
    to_department_name = serializers.CharField(
        source="to_department.name", read_only=True, allow_null=True
    )
    to_location_id = serializers.PrimaryKeyRelatedField(
        source="to_location", queryset=Location.objects.none(), allow_null=True
    )
    to_location_name = serializers.CharField(
        source="to_location.name", read_only=True, allow_null=True
    )
    requested_by_email = serializers.EmailField(source="requested_by.email", read_only=True)
    approved_by_email = serializers.EmailField(
        source="approved_by.email", read_only=True, allow_null=True
    )
    completed_by_email = serializers.EmailField(
        source="completed_by.email", read_only=True, allow_null=True
    )
    rejected_by_email = serializers.EmailField(
        source="rejected_by.email", read_only=True, allow_null=True
    )
    cancelled_by_email = serializers.EmailField(
        source="cancelled_by.email", read_only=True, allow_null=True
    )

    class Meta:
        model = AssetTransfer
        fields = (
            "id",
            "organization_id",
            "asset_id",
            "asset_tag",
            "asset_name",
            "from_department_id",
            "from_department_name",
            "from_location_id",
            "from_location_name",
            "to_department_id",
            "to_department_name",
            "to_location_id",
            "to_location_name",
            "requested_by_email",
            "approved_by_email",
            "completed_by_email",
            "rejected_by_email",
            "cancelled_by_email",
            "requested_at",
            "approved_at",
            "completed_at",
            "rejected_at",
            "cancelled_at",
            "status",
            "reason",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "organization_id",
            "asset_tag",
            "asset_name",
            "from_department_id",
            "from_department_name",
            "from_location_id",
            "from_location_name",
            "to_department_name",
            "to_location_name",
            "requested_by_email",
            "approved_by_email",
            "completed_by_email",
            "rejected_by_email",
            "cancelled_by_email",
            "requested_at",
            "approved_at",
            "completed_at",
            "rejected_at",
            "cancelled_at",
            "status",
            "created_at",
            "updated_at",
        )
        validators = ()

    def get_fields(self):
        fields = super().get_fields()
        user = getattr(self.context.get("request"), "user", None)
        organization_id = getattr(user, "organization_id", None)
        fields["asset_id"].queryset = Asset.objects.filter(organization_id=organization_id)
        fields["to_department_id"].queryset = Department.objects.filter(
            organization_id=organization_id
        )
        fields["to_location_id"].queryset = Location.objects.filter(organization_id=organization_id)
        if self.instance is None:
            fields["to_department_id"].required = True
            fields["to_location_id"].required = True
        else:
            fields["asset_id"].read_only = True
            fields["to_department_id"].read_only = True
            fields["to_location_id"].read_only = True
        return fields
