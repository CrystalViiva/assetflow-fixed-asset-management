"""Append-oriented, generic audit event records."""

import uuid

from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="audit_logs",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=64)
    entity_type = models.CharField(max_length=100)
    entity_id = models.CharField(max_length=64)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    changes = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-timestamp",)
        indexes = [
            models.Index(
                fields=("organization", "entity_type", "entity_id"), name="audit_org_entity_idx"
            ),
            models.Index(
                fields=("organization", "action", "timestamp"), name="audit_org_action_time_idx"
            ),
        ]

    def __str__(self):
        return f"{self.action} {self.entity_type}:{self.entity_id}"
