from rest_framework import serializers

from accounts.models import User
from assets.models import Asset
from organizations.models import Department, Location
from verification.models import (
    ExceptionSeverity,
    PhysicalVerification,
    VerificationCampaign,
    VerificationEvidence,
    VerificationException,
)


class VerificationCampaignSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    department_id = serializers.PrimaryKeyRelatedField(
        source="department", queryset=Department.objects.none(), required=False, allow_null=True
    )
    location_id = serializers.PrimaryKeyRelatedField(
        source="location", queryset=Location.objects.none(), required=False, allow_null=True
    )
    created_by_email = serializers.EmailField(source="created_by.email", read_only=True)
    expected_asset_count = serializers.IntegerField(read_only=True)
    verified_asset_count = serializers.IntegerField(read_only=True)
    unverified_asset_count = serializers.IntegerField(read_only=True)
    exception_count = serializers.IntegerField(read_only=True)
    resolved_exception_count = serializers.IntegerField(read_only=True)
    verification_percentage = serializers.DecimalField(
        max_digits=7, decimal_places=2, read_only=True
    )

    class Meta:
        model = VerificationCampaign
        fields = (
            "id",
            "organization_id",
            "name",
            "description",
            "status",
            "scope_type",
            "department_id",
            "location_id",
            "start_date",
            "due_date",
            "opened_at",
            "completed_at",
            "created_by_email",
            "expected_asset_count",
            "verified_asset_count",
            "unverified_asset_count",
            "exception_count",
            "resolved_exception_count",
            "verification_percentage",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "organization_id",
            "status",
            "opened_at",
            "completed_at",
            "created_by_email",
            "expected_asset_count",
            "verified_asset_count",
            "unverified_asset_count",
            "exception_count",
            "resolved_exception_count",
            "verification_percentage",
            "created_at",
            "updated_at",
        )

    def get_fields(self):
        fields = super().get_fields()
        org_id = getattr(
            getattr(self.context.get("request"), "user", None), "organization_id", None
        )
        fields["department_id"].queryset = Department.objects.filter(organization_id=org_id)
        fields["location_id"].queryset = Location.objects.filter(organization_id=org_id)
        return fields


class VerificationExceptionSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = VerificationException
        fields = ("id", "exception_type", "severity", "status", "description")


class PhysicalVerificationSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    campaign_id = serializers.PrimaryKeyRelatedField(
        source="campaign", queryset=VerificationCampaign.objects.none()
    )
    asset_id = serializers.PrimaryKeyRelatedField(
        source="asset", queryset=Asset.objects.none(), required=False, allow_null=True
    )
    observed_location_id = serializers.PrimaryKeyRelatedField(
        source="observed_location",
        queryset=Location.objects.none(),
        required=False,
        allow_null=True,
    )
    observed_department_id = serializers.PrimaryKeyRelatedField(
        source="observed_department",
        queryset=Department.objects.none(),
        required=False,
        allow_null=True,
    )
    observed_custodian_id = serializers.PrimaryKeyRelatedField(
        source="observed_custodian", queryset=User.objects.none(), required=False, allow_null=True
    )
    verified_by_email = serializers.EmailField(source="verified_by.email", read_only=True)
    asset_tag = serializers.CharField(source="asset.asset_tag", read_only=True, allow_null=True)
    exceptions = VerificationExceptionSummarySerializer(many=True, read_only=True)

    class Meta:
        model = PhysicalVerification
        fields = (
            "id",
            "organization_id",
            "campaign_id",
            "asset_id",
            "asset_tag",
            "verified_at",
            "verified_by_email",
            "result",
            "observed_location_id",
            "observed_department_id",
            "observed_custodian_id",
            "observed_condition",
            "observed_asset_tag",
            "observed_description",
            "notes",
            "exceptions",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "organization_id",
            "verified_at",
            "verified_by_email",
            "result",
            "asset_tag",
            "exceptions",
            "created_at",
            "updated_at",
        )

    def get_fields(self):
        fields = super().get_fields()
        org_id = getattr(
            getattr(self.context.get("request"), "user", None), "organization_id", None
        )
        fields["campaign_id"].queryset = VerificationCampaign.objects.filter(organization_id=org_id)
        fields["asset_id"].queryset = Asset.objects.filter(organization_id=org_id)
        fields["observed_location_id"].queryset = Location.objects.filter(organization_id=org_id)
        fields["observed_department_id"].queryset = Department.objects.filter(
            organization_id=org_id
        )
        fields["observed_custodian_id"].queryset = User.objects.filter(organization_id=org_id)
        return fields


class VerificationExceptionSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    campaign_id = serializers.UUIDField(read_only=True)
    verification_id = serializers.UUIDField(read_only=True)
    asset_id = serializers.UUIDField(read_only=True, allow_null=True)
    asset_tag = serializers.CharField(source="asset.asset_tag", read_only=True, allow_null=True)
    assigned_to_id = serializers.UUIDField(read_only=True, allow_null=True)
    assigned_to_email = serializers.EmailField(
        source="assigned_to.email", read_only=True, allow_null=True
    )
    resolved_by_email = serializers.EmailField(
        source="resolved_by.email", read_only=True, allow_null=True
    )

    class Meta:
        model = VerificationException
        fields = (
            "id",
            "organization_id",
            "campaign_id",
            "verification_id",
            "asset_id",
            "asset_tag",
            "exception_type",
            "severity",
            "status",
            "description",
            "assigned_to_id",
            "assigned_to_email",
            "assigned_at",
            "started_at",
            "resolution_notes",
            "resolution_reference",
            "resolved_by_email",
            "resolved_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class VerificationEvidenceSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    verification_id = serializers.PrimaryKeyRelatedField(
        source="verification", queryset=PhysicalVerification.objects.none()
    )
    exception_id = serializers.PrimaryKeyRelatedField(
        source="exception",
        queryset=VerificationException.objects.none(),
        required=False,
        allow_null=True,
    )
    captured_by_email = serializers.EmailField(source="captured_by.email", read_only=True)

    class Meta:
        model = VerificationEvidence
        fields = (
            "id",
            "organization_id",
            "verification_id",
            "exception_id",
            "evidence_type",
            "file_name",
            "content_type",
            "storage_key",
            "external_reference",
            "captured_at",
            "captured_by_email",
            "description",
            "created_at",
        )
        read_only_fields = (
            "id",
            "organization_id",
            "captured_at",
            "captured_by_email",
            "created_at",
        )

    def get_fields(self):
        fields = super().get_fields()
        org_id = getattr(
            getattr(self.context.get("request"), "user", None), "organization_id", None
        )
        fields["verification_id"].queryset = PhysicalVerification.objects.filter(
            organization_id=org_id
        )
        fields["exception_id"].queryset = VerificationException.objects.filter(
            organization_id=org_id
        )
        return fields


class ExceptionAssignmentSerializer(serializers.Serializer):
    assigned_to_id = serializers.PrimaryKeyRelatedField(
        source="assigned_to", queryset=User.objects.none()
    )

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        user = getattr(request, "user", None)
        queryset = User.objects.filter(organization_id=getattr(user, "organization_id", None))
        if getattr(user, "role", None) == "DEPARTMENT_MANAGER":
            queryset = queryset.filter(department_id=user.department_id)
        fields["assigned_to_id"].queryset = queryset
        return fields


class ExceptionResolutionSerializer(serializers.Serializer):
    resolution_notes = serializers.CharField()
    resolution_reference = serializers.CharField(required=False, allow_blank=True, max_length=200)


class ManualVerificationExceptionSerializer(serializers.Serializer):
    verification_id = serializers.PrimaryKeyRelatedField(
        source="verification", queryset=PhysicalVerification.objects.none()
    )
    description = serializers.CharField()
    severity = serializers.ChoiceField(
        choices=ExceptionSeverity.choices, default=ExceptionSeverity.MEDIUM
    )

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        user = getattr(request, "user", None)
        fields["verification_id"].queryset = PhysicalVerification.objects.filter(
            organization_id=getattr(user, "organization_id", None)
        )
        return fields


class MissingReconciliationResultSerializer(serializers.Serializer):
    created_count = serializers.IntegerField()
