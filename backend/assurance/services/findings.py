from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from assurance.models import AssuranceFinding, FindingStatus
from assurance.services.audit import audit


def _transition(*, finding_id, actor, status, notes, action, ip_address=None):
    if not actor.organization_id:
        raise ValidationError({"organization": "The user must belong to an organization."})
    with transaction.atomic():
        try:
            finding = AssuranceFinding.objects.select_for_update(of=("self",)).get(
                pk=finding_id, organization_id=actor.organization_id
            )
        except AssuranceFinding.DoesNotExist as exc:
            raise ValidationError(
                {"finding": "Assurance finding was not found in your organization."}
            ) from exc
        if finding.status != FindingStatus.UNDER_REVIEW:
            raise ValidationError({"status": "Review the finding before closing it."})
        if not notes.strip():
            raise ValidationError({"resolution_notes": "Resolution notes are required."})
        before = finding.status
        finding.status = status
        finding.resolved_at = timezone.now()
        finding.resolved_by = actor
        finding.resolution_notes = notes.strip()
        finding.full_clean()
        finding.save(
            update_fields=("status", "resolved_at", "resolved_by", "resolution_notes", "updated_at")
        )
        audit(
            organization=finding.organization,
            actor=actor,
            action=action,
            entity_type="ASSURANCE_FINDING",
            entity_id=finding.pk,
            changes={"status": {"from": before, "to": status}},
            metadata={"resolution_notes": finding.resolution_notes},
            ip_address=ip_address,
        )
    return finding


def review_finding(*, finding_id, actor, ip_address=None):
    if not actor.organization_id:
        raise ValidationError({"organization": "The user must belong to an organization."})
    with transaction.atomic():
        try:
            finding = AssuranceFinding.objects.select_for_update(of=("self",)).get(
                pk=finding_id, organization_id=actor.organization_id
            )
        except AssuranceFinding.DoesNotExist as exc:
            raise ValidationError(
                {"finding": "Finding was not found in your organization."}
            ) from exc
        if finding.status != FindingStatus.OPEN:
            raise ValidationError({"status": "Only open findings can enter review."})
        finding.status = FindingStatus.UNDER_REVIEW
        finding.save(update_fields=("status", "updated_at"))
        audit(
            organization=finding.organization,
            actor=actor,
            action="ASSURANCE_FINDING_REVIEWED",
            entity_type="ASSURANCE_FINDING",
            entity_id=finding.pk,
            changes={"status": {"from": FindingStatus.OPEN, "to": FindingStatus.UNDER_REVIEW}},
            ip_address=ip_address,
        )
    return finding


def resolve_finding(*, finding_id, actor, resolution_notes, ip_address=None):
    return _transition(
        finding_id=finding_id,
        actor=actor,
        status=FindingStatus.RESOLVED,
        notes=resolution_notes,
        action="ASSURANCE_FINDING_RESOLVED",
        ip_address=ip_address,
    )


def accept_finding(*, finding_id, actor, resolution_notes, ip_address=None):
    return _transition(
        finding_id=finding_id,
        actor=actor,
        status=FindingStatus.ACCEPTED,
        notes=resolution_notes,
        action="ASSURANCE_FINDING_ACCEPTED",
        ip_address=ip_address,
    )


def reject_finding(*, finding_id, actor, resolution_notes, ip_address=None):
    return _transition(
        finding_id=finding_id,
        actor=actor,
        status=FindingStatus.REJECTED,
        notes=resolution_notes,
        action="ASSURANCE_FINDING_REJECTED",
        ip_address=ip_address,
    )
