from audit.services import record_event


def audit(
    *,
    organization,
    actor,
    action,
    entity_type,
    entity_id,
    changes=None,
    metadata=None,
    ip_address=None,
):
    return record_event(
        organization=organization,
        user=actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        changes=changes or {},
        metadata=metadata or {},
        ip_address=ip_address,
    )
