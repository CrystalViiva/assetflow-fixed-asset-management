"""Small service API for domain services to record audit events."""

from audit.models import AuditLog

SENSITIVE_KEY_PARTS = (
    "password",
    "token",
    "authorization",
    "api_key",
    "secret",
    "credential",
    "cookie",
)


def public_audit_value(value):
    """Return JSON metadata with obvious credential-bearing keys removed."""
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            normalized = str(key).lower().replace("-", "_")
            if any(part in normalized for part in SENSITIVE_KEY_PARTS):
                result[str(key)] = "[REDACTED]"
            else:
                result[str(key)] = public_audit_value(item)
        return result
    if isinstance(value, list):
        return [public_audit_value(item) for item in value]
    return value


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
