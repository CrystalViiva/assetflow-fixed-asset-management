from rest_framework import serializers

from reporting.models import ReportSnapshot, ReportSnapshotRow, ReportType


class ReportCatalogSerializer(serializers.Serializer):
    report_type = serializers.ChoiceField(choices=ReportType.choices)
    label = serializers.CharField()
    result_url = serializers.CharField()
    snapshot_supported = serializers.BooleanField(default=True)
    columns = serializers.ListField(child=serializers.CharField())
    filters = serializers.ListField(child=serializers.CharField())


class PaginatedReportRowsSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = serializers.ListField(child=serializers.JSONField())


class ReportSnapshotRequestSerializer(serializers.Serializer):
    report_type = serializers.ChoiceField(choices=ReportType.choices)
    filters = serializers.JSONField(required=False, default=dict)
    idempotency_key = serializers.UUIDField()


class ReportSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportSnapshot
        fields = (
            "id",
            "report_type",
            "parameters",
            "scope_department_id",
            "status",
            "requested_at",
            "started_at",
            "as_of",
            "generated_at",
            "failed_at",
            "row_count",
            "summary",
            "schema_version",
            "failure_class",
            "failure_message",
        )
        read_only_fields = fields


class ReportSnapshotRowSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportSnapshotRow
        fields = ("ordinal", "source_id", "payload")
        read_only_fields = fields


class PaginatedReportSnapshotsSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = ReportSnapshotSerializer(many=True)


class PaginatedReportSnapshotRowsSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = ReportSnapshotRowSerializer(many=True)
