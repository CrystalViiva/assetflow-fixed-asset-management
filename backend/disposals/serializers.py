from rest_framework import serializers

from assets.models import Asset
from disposals.models import Disposal


class DisposalSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    asset_id = serializers.PrimaryKeyRelatedField(source="asset", queryset=Asset.objects.none())
    asset_tag = serializers.CharField(source="asset.asset_tag", read_only=True)
    asset_name = serializers.CharField(source="asset.name", read_only=True)
    department_name = serializers.CharField(
        source="asset.department.name", read_only=True, allow_null=True
    )
    location_name = serializers.CharField(
        source="asset.location.name", read_only=True, allow_null=True
    )
    requested_by_email = serializers.EmailField(source="requested_by.email", read_only=True)
    submitted_by_email = serializers.EmailField(
        source="submitted_by.email", read_only=True, allow_null=True
    )
    approved_by_email = serializers.EmailField(
        source="approved_by.email", read_only=True, allow_null=True
    )

    class Meta:
        model = Disposal
        fields = (
            "id",
            "organization_id",
            "asset_id",
            "asset_tag",
            "asset_name",
            "department_name",
            "location_name",
            "disposal_date",
            "disposal_method",
            "reason",
            "proceeds",
            "currency",
            "capitalized_cost_at_disposal",
            "accumulated_depreciation_at_disposal",
            "carrying_amount",
            "gain_or_loss",
            "status",
            "requested_by_email",
            "submitted_by_email",
            "submitted_at",
            "approved_by_email",
            "approved_at",
            "rejected_by",
            "rejected_at",
            "cancelled_by",
            "cancelled_at",
            "completed_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "organization_id",
            "asset_tag",
            "asset_name",
            "department_name",
            "location_name",
            "capitalized_cost_at_disposal",
            "accumulated_depreciation_at_disposal",
            "carrying_amount",
            "gain_or_loss",
            "status",
            "requested_by_email",
            "submitted_by_email",
            "submitted_at",
            "approved_by_email",
            "approved_at",
            "rejected_by",
            "rejected_at",
            "cancelled_by",
            "cancelled_at",
            "completed_at",
            "created_at",
            "updated_at",
        )

    def get_fields(self):
        fields = super().get_fields()
        organization = getattr(
            getattr(self.context.get("request"), "user", None), "organization", None
        )
        organization_id = getattr(organization, "pk", None)
        fields["asset_id"].queryset = Asset.objects.filter(organization_id=organization_id)
        fields["currency"].required = False
        if organization is not None:
            fields["currency"].default = organization.currency
        if self.instance is not None:
            fields["asset_id"].read_only = True
        return fields


class DisposalReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default="")
