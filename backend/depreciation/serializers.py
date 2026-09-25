from rest_framework import serializers

from depreciation.models import AccountingPeriod, DepreciationEntry, DepreciationSchedule


class AccountingPeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountingPeriod
        fields = (
            "id",
            "year",
            "month",
            "status",
            "opened_at",
            "closed_at",
            "closed_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "status",
            "opened_at",
            "closed_at",
            "closed_by",
            "created_at",
            "updated_at",
        )


class DepreciationScheduleSerializer(serializers.ModelSerializer):
    asset_id = serializers.UUIDField(source="asset.id", read_only=True)
    asset_tag = serializers.CharField(source="asset.asset_tag", read_only=True)

    class Meta:
        model = DepreciationSchedule
        fields = (
            "id",
            "organization",
            "asset_id",
            "asset_tag",
            "method",
            "capitalized_cost",
            "depreciable_base",
            "residual_value",
            "useful_life_months",
            "start_date",
            "end_date",
            "periodic_depreciation",
            "status",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class ScheduleCreateSerializer(serializers.Serializer):
    asset_id = serializers.UUIDField()


class DepreciationEntrySerializer(serializers.ModelSerializer):
    asset_tag = serializers.CharField(source="asset.asset_tag", read_only=True)
    year = serializers.IntegerField(source="accounting_period.year", read_only=True)
    month = serializers.IntegerField(source="accounting_period.month", read_only=True)

    class Meta:
        model = DepreciationEntry
        fields = (
            "id",
            "asset",
            "asset_tag",
            "schedule",
            "accounting_period",
            "year",
            "month",
            "opening_book_value",
            "depreciation_amount",
            "accumulated_depreciation",
            "closing_book_value",
            "posted_at",
            "created_at",
            "created_by",
        )
        read_only_fields = fields


class PostDepreciationSerializer(serializers.Serializer):
    asset_id = serializers.UUIDField()
    period_id = serializers.UUIDField()
