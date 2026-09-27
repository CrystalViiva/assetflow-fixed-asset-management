import pytest
from django.core.exceptions import ValidationError

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


@pytest.mark.django_db
def test_audit_events_are_append_only_through_ordinary_orm_operations():
    organization = Organization.objects.create(name="Audit Org", code="AUDIT-ORG")
    event = record_event(
        organization=organization,
        action="ASSET_CREATED",
        entity_type="ASSET",
        entity_id="asset-456",
    )

    event.action = "ASSET_DELETED"
    with pytest.raises(ValidationError, match="immutable"):
        event.save()
    with pytest.raises(ValidationError, match="immutable"):
        AuditLog.objects.filter(pk=event.pk).update(action="ASSET_DELETED")
    with pytest.raises(ValidationError, match="cannot be deleted"):
        event.delete()
    with pytest.raises(ValidationError, match="cannot be deleted"):
        AuditLog.objects.filter(pk=event.pk).delete()

    assert AuditLog.objects.get(pk=event.pk).action == "ASSET_CREATED"


@pytest.mark.django_db
def test_deleting_actor_preserves_audit_event_and_nulls_actor_link():
    organization = Organization.objects.create(name="Audit Actor Org", code="AUDIT-ACTOR")
    user = User.objects.create_user("audit-actor@example.test", "test-password")
    event = record_event(
        organization=organization,
        user=user,
        action="ASSET_CREATED",
        entity_type="ASSET",
        entity_id="asset-789",
    )

    user.delete()

    event.refresh_from_db()
    assert event.user_id is None
