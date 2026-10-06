from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from audit.models import AuditLog
from audit.services import public_audit_value


class AuditEventSerializer(serializers.ModelSerializer):
    actor_email = serializers.EmailField(source="user.email", allow_null=True, read_only=True)
    changes = serializers.SerializerMethodField()
    metadata = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = (
            "id",
            "timestamp",
            "actor_email",
            "action",
            "entity_type",
            "entity_id",
            "changes",
            "metadata",
        )
        read_only_fields = fields

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_changes(self, obj) -> dict:
        return public_audit_value(obj.changes)

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_metadata(self, obj) -> dict:
        return public_audit_value(obj.metadata)


class PaginatedAuditEventsSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = AuditEventSerializer(many=True)
