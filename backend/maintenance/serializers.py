from rest_framework import serializers

from accounts.models import User
from assets.models import Asset
from maintenance.models import (
    MaintenanceCost,
    MaintenancePlan,
    MaintenanceRecord,
    WorkOrder,
)


class MaintenancePlanSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    asset_id = serializers.PrimaryKeyRelatedField(source="asset", queryset=Asset.objects.none())
    asset_tag = serializers.CharField(source="asset.asset_tag", read_only=True)
    created_by_email = serializers.EmailField(source="created_by.email", read_only=True)

    class Meta:
        model = MaintenancePlan
        fields = (
            "id",
            "organization_id",
            "asset_id",
            "asset_tag",
            "maintenance_type",
            "frequency_value",
            "frequency_unit",
            "next_due_date",
            "active",
            "instructions",
            "created_by_email",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "organization_id",
            "asset_tag",
            "created_by_email",
            "created_at",
            "updated_at",
        )

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        fields["asset_id"].queryset = Asset.objects.filter(
            organization_id=getattr(getattr(request, "user", None), "organization_id", None)
        )
        if self.instance is not None:
            fields["asset_id"].read_only = True
        return fields


class WorkOrderSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    asset_id = serializers.PrimaryKeyRelatedField(source="asset", queryset=Asset.objects.none())
    asset_tag = serializers.CharField(source="asset.asset_tag", read_only=True)
    requested_by_email = serializers.EmailField(source="requested_by.email", read_only=True)
    assigned_to_id = serializers.PrimaryKeyRelatedField(
        source="assigned_to", queryset=User.objects.none(), required=False, allow_null=True
    )
    assigned_to_email = serializers.EmailField(
        source="assigned_to.email", read_only=True, allow_null=True
    )

    class Meta:
        model = WorkOrder
        fields = (
            "id",
            "organization_id",
            "work_order_number",
            "asset_id",
            "asset_tag",
            "maintenance_type",
            "priority",
            "status",
            "description",
            "diagnosis",
            "resolution",
            "requested_by_email",
            "assigned_to_id",
            "assigned_to_email",
            "due_date",
            "opened_at",
            "started_at",
            "completed_at",
            "cancelled_at",
            "completion_notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "organization_id",
            "work_order_number",
            "asset_tag",
            "status",
            "requested_by_email",
            "assigned_to_id",
            "assigned_to_email",
            "opened_at",
            "started_at",
            "completed_at",
            "cancelled_at",
            "resolution",
            "completion_notes",
            "created_at",
            "updated_at",
        )

    def get_fields(self):
        fields = super().get_fields()
        organization_id = getattr(
            getattr(self.context.get("request"), "user", None), "organization_id", None
        )
        fields["asset_id"].queryset = Asset.objects.filter(organization_id=organization_id)
        fields["assigned_to_id"].queryset = User.objects.filter(organization_id=organization_id)
        if self.instance is not None:
            fields["asset_id"].read_only = True
            fields["assigned_to_id"].read_only = True
            for name in ("maintenance_type", "priority", "description", "diagnosis", "due_date"):
                fields[name].read_only = True
        return fields


class AssignWorkOrderSerializer(serializers.Serializer):
    assigned_to_id = serializers.PrimaryKeyRelatedField(
        source="assigned_to", queryset=User.objects.none()
    )

    def get_fields(self):
        fields = super().get_fields()
        organization_id = getattr(
            getattr(self.context.get("request"), "user", None), "organization_id", None
        )
        fields["assigned_to_id"].queryset = User.objects.filter(organization_id=organization_id)
        return fields


class CompleteWorkOrderSerializer(serializers.Serializer):
    resolution = serializers.CharField()
    completion_notes = serializers.CharField(required=False, allow_blank=True, default="")
    downtime_minutes = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    performed_by_id = serializers.PrimaryKeyRelatedField(
        source="performed_by", queryset=User.objects.none(), required=False, allow_null=True
    )
    maintenance_date = serializers.DateField(required=False)

    def get_fields(self):
        fields = super().get_fields()
        organization_id = getattr(
            getattr(self.context.get("request"), "user", None), "organization_id", None
        )
        fields["performed_by_id"].queryset = User.objects.filter(organization_id=organization_id)
        return fields


class CancelWorkOrderSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class MaintenanceCostSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    work_order_id = serializers.PrimaryKeyRelatedField(
        source="work_order", queryset=WorkOrder.objects.none()
    )
    work_order_number = serializers.CharField(source="work_order.work_order_number", read_only=True)
    created_by_email = serializers.EmailField(source="created_by.email", read_only=True)

    class Meta:
        model = MaintenanceCost
        fields = (
            "id",
            "organization_id",
            "work_order_id",
            "work_order_number",
            "cost_type",
            "description",
            "quantity",
            "unit_cost",
            "total_cost",
            "vendor_reference",
            "incurred_at",
            "created_by_email",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "organization_id",
            "work_order_number",
            "total_cost",
            "created_by_email",
            "created_at",
            "updated_at",
        )

    def get_fields(self):
        fields = super().get_fields()
        organization_id = getattr(
            getattr(self.context.get("request"), "user", None), "organization_id", None
        )
        fields["work_order_id"].queryset = WorkOrder.objects.filter(organization_id=organization_id)
        return fields


class MaintenanceRecordSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    asset_tag = serializers.CharField(source="asset.asset_tag", read_only=True)
    work_order_number = serializers.CharField(source="work_order.work_order_number", read_only=True)
    performed_by_email = serializers.EmailField(
        source="performed_by.email", read_only=True, allow_null=True
    )

    class Meta:
        model = MaintenanceRecord
        fields = (
            "id",
            "organization_id",
            "asset",
            "asset_tag",
            "work_order",
            "work_order_number",
            "maintenance_date",
            "maintenance_type",
            "summary",
            "total_cost",
            "downtime_minutes",
            "performed_by_email",
            "created_at",
        )
        read_only_fields = fields


class WorkOrderCompletionResultSerializer(serializers.Serializer):
    work_order = WorkOrderSerializer()
    maintenance_record = MaintenanceRecordSerializer()
