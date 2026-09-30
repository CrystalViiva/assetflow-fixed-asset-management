from rest_framework import serializers

from assurance.models import (
    AssuranceFinding,
    AssuranceFindingOccurrence,
    AssuranceRun,
)
from verification.models import VerificationCampaign


class AssuranceRunSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    verification_campaign_id = serializers.PrimaryKeyRelatedField(
        source="verification_campaign",
        queryset=VerificationCampaign.objects.none(),
        required=False,
        allow_null=True,
    )
    started_by_email = serializers.EmailField(
        source="started_by.email", read_only=True, allow_null=True
    )
    completed_by_email = serializers.EmailField(
        source="completed_by.email", read_only=True, allow_null=True
    )

    class Meta:
        model = AssuranceRun
        fields = (
            "id",
            "organization_id",
            "run_type",
            "status",
            "verification_campaign_id",
            "stale_after_days",
            "scheduled_for",
            "started_at",
            "completed_at",
            "started_by_email",
            "completed_by_email",
            "assets_evaluated",
            "findings_generated",
            "findings_open",
            "findings_resolved",
            "failure_message",
            "execution_phase",
            "captured_at",
            "sealed_at",
            "executor_version",
            "input_schema_version",
            "population_count",
            "unit_count",
            "units_completed",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "organization_id",
            "status",
            "started_at",
            "completed_at",
            "scheduled_for",
            "started_by_email",
            "completed_by_email",
            "assets_evaluated",
            "findings_generated",
            "findings_open",
            "findings_resolved",
            "failure_message",
            "execution_phase",
            "captured_at",
            "sealed_at",
            "executor_version",
            "input_schema_version",
            "population_count",
            "unit_count",
            "units_completed",
            "created_at",
            "updated_at",
        )

    def get_fields(self):
        fields = super().get_fields()
        user = getattr(self.context.get("request"), "user", None)
        fields["verification_campaign_id"].queryset = VerificationCampaign.objects.filter(
            organization_id=getattr(user, "organization_id", None)
        )
        return fields


class AssuranceFindingOccurrenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssuranceFindingOccurrence
        fields = (
            "id",
            "assurance_run",
            "detected_at",
            "expected_value",
            "observed_value",
            "description",
        )
        read_only_fields = fields


class AssuranceFindingSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    asset_tag = serializers.CharField(source="asset.asset_tag", read_only=True, allow_null=True)
    asset_name = serializers.CharField(source="asset.name", read_only=True, allow_null=True)
    department_name = serializers.CharField(
        source="asset.department.name", read_only=True, allow_null=True
    )
    location_name = serializers.CharField(
        source="asset.location.name", read_only=True, allow_null=True
    )
    occurrences = AssuranceFindingOccurrenceSerializer(many=True, read_only=True)
    resolved_by_email = serializers.EmailField(
        source="resolved_by.email", read_only=True, allow_null=True
    )

    class Meta:
        model = AssuranceFinding
        fields = (
            "id",
            "organization_id",
            "assurance_run",
            "last_detected_run",
            "asset",
            "asset_tag",
            "asset_name",
            "physical_verification",
            "department_name",
            "location_name",
            "identity_key",
            "finding_type",
            "severity",
            "status",
            "source",
            "expected_value",
            "observed_value",
            "description",
            "occurrence_count",
            "first_detected_at",
            "last_detected_at",
            "resolved_at",
            "resolved_by_email",
            "resolution_notes",
            "occurrences",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class FindingResolutionSerializer(serializers.Serializer):
    resolution_notes = serializers.CharField()


class AssuranceSummarySerializer(serializers.Serializer):
    runs = serializers.IntegerField()
    assets_evaluated = serializers.IntegerField()
    total_findings = serializers.IntegerField()
    findings_open = serializers.IntegerField()
    findings_resolved = serializers.IntegerField()
    recurring_findings = serializers.IntegerField()
    assets_with_multiple_findings = serializers.IntegerField()
    by_severity = serializers.ListField(child=serializers.DictField())
    by_type = serializers.ListField(child=serializers.DictField())
    by_status = serializers.ListField(child=serializers.DictField())
