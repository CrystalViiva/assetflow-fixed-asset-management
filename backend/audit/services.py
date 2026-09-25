"""Small service API for domain services to record audit events."""

from audit.models import AuditLog


def record_event(
    *,
    organization,
    action,
    entity_type,
    entity_id,
    user=None,
    ip_address=None,
    changes=None,
    metadata=None,
):
    """Persist one structured audit event for a domain operation."""
    return AuditLog.objects.create(
        organization=organization,
        user=user,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        ip_address=ip_address,
        changes=changes or {},
        metadata=metadata or {},
    )
