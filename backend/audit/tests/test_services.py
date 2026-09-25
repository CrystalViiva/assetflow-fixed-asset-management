import pytest

from accounts.models import User
from audit.models import AuditLog
from audit.services import record_event
from organizations.models import Organization


@pytest.mark.django_db
def test_record_event_persists_json_changes_and_metadata():
    organization = Organization.objects.create(name="Acme Nigeria", code="ACME")
    user = User.objects.create_user("accountant@example.com", "strong-password")

    event = record_event(
        organization=organization,
        user=user,
        action="ASSET_CREATED",
        entity_type="ASSET",
        entity_id="asset-123",
        ip_address="192.0.2.10",
        changes={"status": {"from": "DRAFT", "to": "ACTIVE"}},
        metadata={"source": "api"},
    )

    saved = AuditLog.objects.get(pk=event.pk)
    assert saved.organization == organization
    assert saved.user == user
    assert saved.changes == {"status": {"from": "DRAFT", "to": "ACTIVE"}}
    assert saved.metadata == {"source": "api"}
