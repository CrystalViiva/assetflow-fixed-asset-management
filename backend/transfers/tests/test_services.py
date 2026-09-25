from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, close_old_connections, connections, transaction
from django.utils import timezone

from assets.models import AssetStatus
from audit.models import AuditLog
from transfers.models import AssetAssignment, AssetTransfer, TransferStatus
from transfers.services import (
    approve_transfer,
    assign_asset,
    cancel_transfer,
    complete_transfer,
    reject_transfer,
    request_transfer,
    return_asset,
)


@pytest.mark.django_db
def test_assignment_opens_custody_and_updates_explicit_asset_placement(
    asset_factory, asset_manager, employee, other_department, other_location
):
    asset = asset_factory()
    assignment = assign_asset(
        asset_id=asset.pk,
        actor=asset_manager,
        assigned_to=employee,
        department=other_department,
        location=other_location,
    )
    asset.refresh_from_db()
    assert assignment.assigned_to == employee
    assert assignment.department == other_department
    assert assignment.location == other_location
    assert asset.department == other_department
    assert asset.location == other_location
    assert AuditLog.objects.get(action="ASSET_ASSIGNED").entity_id == str(assignment.pk)


@pytest.mark.django_db
def test_assignment_can_record_unassigned_custody(asset_factory, asset_manager):
    asset = asset_factory()
    assignment = assign_asset(asset_id=asset.pk, actor=asset_manager)
    assert assignment.assigned_to is None
    assert assignment.department_id == asset.department_id
    assert assignment.location_id == asset.location_id


@pytest.mark.django_db
def test_only_one_active_assignment_database_constraint(asset_factory, asset_manager, employee):
    asset = asset_factory()
    first = assign_asset(asset_id=asset.pk, actor=asset_manager, assigned_to=employee)
    with pytest.raises(IntegrityError), transaction.atomic():
        AssetAssignment.objects.create(
            organization=asset.organization,
            asset=asset,
            assigned_to=employee,
            department=asset.department,
            location=asset.location,
            created_by=asset_manager,
        )
    assert AssetAssignment.objects.filter(asset=asset, returned_at__isnull=True).get() == first


@pytest.mark.django_db
def test_return_closes_assignment_and_preserves_immutable_history(
    asset_factory, asset_manager, employee
):
    asset = asset_factory()
    assignment = assign_asset(asset_id=asset.pk, actor=asset_manager, assigned_to=employee)
    returned = return_asset(asset_id=asset.pk, actor=asset_manager, assignment_id=assignment.pk)
    returned_at = returned.returned_at
    returned.notes = "silently edited history"
    with pytest.raises(ValidationError, match="immutable"):
        returned.save()
    assert AssetAssignment.objects.get(pk=assignment.pk).returned_at == returned_at
    assert not AssetAssignment.objects.filter(asset=asset, returned_at__isnull=True).exists()
    assert AuditLog.objects.filter(action="ASSET_ASSIGNMENT_RETURNED").exists()


@pytest.mark.django_db
def test_assignment_rejects_disposed_cross_org_and_invalid_date(
    asset_factory, asset_manager, employee, other_org_user, other_org_department
):
    disposed = asset_factory(asset_tag="DISPOSED", status=AssetStatus.DISPOSED)
    with pytest.raises(ValidationError, match="lifecycle"):
        assign_asset(asset_id=disposed.pk, actor=asset_manager)

    asset = asset_factory(asset_tag="NORMAL")
    for values in (
        {"assigned_to": other_org_user},
        {"department": other_org_department},
    ):
        with pytest.raises(ValidationError):
            assign_asset(asset_id=asset.pk, actor=asset_manager, **values)

    assigned_at = timezone.now()
    invalid = AssetAssignment(
        organization=asset.organization,
        asset=asset,
        assigned_to=employee,
        department=asset.department,
        location=asset.location,
        assigned_at=assigned_at,
        returned_at=assigned_at - timedelta(seconds=1),
        returned_by=asset_manager,
        created_by=asset_manager,
    )
    with pytest.raises(ValidationError, match="precede"):
        invalid.full_clean()


@pytest.mark.django_db
def test_assignment_audit_failure_rolls_back_assignment_and_asset_changes(
    asset_factory, asset_manager, employee, other_department
):
    asset = asset_factory()
    with patch("transfers.services.record_event", side_effect=RuntimeError("audit failed")):
        with pytest.raises(RuntimeError):
            assign_asset(
                asset_id=asset.pk,
                actor=asset_manager,
                assigned_to=employee,
                department=other_department,
            )
    asset.refresh_from_db()
    assert asset.department_id != other_department.pk
    assert not AssetAssignment.objects.exists()


@pytest.mark.django_db
def test_transfer_request_approval_and_completion_updates_snapshot_but_not_custody(
    asset_factory, asset_manager, employee, other_department, other_location
):
    asset = asset_factory()
    assignment = assign_asset(asset_id=asset.pk, actor=asset_manager, assigned_to=employee)
    transfer = request_transfer(
        asset_id=asset.pk,
        actor=asset_manager,
        to_department=other_department,
        to_location=other_location,
        reason="Move to new facility",
    )
    assert transfer.from_department_id == asset.department_id
    approved = approve_transfer(transfer_id=transfer.pk, actor=asset_manager)
    assert approved.status == TransferStatus.APPROVED
    completed = complete_transfer(transfer_id=transfer.pk, actor=asset_manager)
    asset.refresh_from_db()
    assignment.refresh_from_db()
    assert completed.status == TransferStatus.COMPLETED
    assert asset.department_id == other_department.pk
    assert asset.location_id == other_location.pk
    assert asset.status == AssetStatus.ACTIVE
    assert assignment.returned_at is None
    assert assignment.assigned_to == employee
    assert AuditLog.objects.filter(action="ASSET_TRANSFER_REQUESTED").exists()
    assert AuditLog.objects.filter(action="ASSET_TRANSFER_APPROVED").exists()
    assert AuditLog.objects.filter(action="ASSET_TRANSFER_COMPLETED").exists()


@pytest.mark.django_db
def test_transfer_reject_cancel_and_invalid_transition(
    transfer_request, asset_factory, asset_manager
):
    rejected = transfer_request()
    result = reject_transfer(transfer_id=rejected.pk, actor=asset_manager)
    assert result.status == TransferStatus.REJECTED
    with pytest.raises(ValidationError):
        complete_transfer(transfer_id=rejected.pk, actor=asset_manager)

    cancelled = transfer_request(asset=asset_factory(asset_tag="AST-CANCEL"))
    result = cancel_transfer(transfer_id=cancelled.pk, actor=asset_manager)
    assert result.status == TransferStatus.CANCELLED
    with pytest.raises(ValidationError):
        approve_transfer(transfer_id=cancelled.pk, actor=asset_manager)
    assert AuditLog.objects.filter(action="ASSET_TRANSFER_REJECTED").count() == 1
    assert AuditLog.objects.filter(action="ASSET_TRANSFER_CANCELLED").count() == 1


@pytest.mark.django_db
def test_transfer_rejects_noop_cross_org_and_source_state_changes(
    transfer_request,
    asset_factory,
    asset_manager,
    department,
    location,
    other_department,
    other_org_department,
    other_org_location,
):
    asset = asset_factory()
    with pytest.raises(ValidationError, match="differ"):
        request_transfer(
            asset_id=asset.pk,
            actor=asset_manager,
            to_department=department,
            to_location=location,
            reason="No movement",
        )
    for values in (
        {"to_department": other_org_department},
        {"to_location": other_org_location},
    ):
        with pytest.raises(ValidationError, match="organization"):
            request_transfer(asset_id=asset.pk, actor=asset_manager, reason="invalid", **values)

    transfer = transfer_request(asset=asset)
    approve_transfer(transfer_id=transfer.pk, actor=asset_manager)
    asset.department = other_department
    asset.save(update_fields=("department", "updated_at"))
    with pytest.raises(ValidationError, match="changed"):
        complete_transfer(transfer_id=transfer.pk, actor=asset_manager)
    assert AssetTransfer.objects.get(pk=transfer.pk).status == TransferStatus.APPROVED


@pytest.mark.django_db
def test_completed_transfer_is_immutable_and_audit_failure_rolls_back_completion(
    transfer_request, asset_manager
):
    transfer = transfer_request()
    approve_transfer(transfer_id=transfer.pk, actor=asset_manager)
    with patch("transfers.services.record_event", side_effect=RuntimeError("audit failed")):
        with pytest.raises(RuntimeError):
            complete_transfer(transfer_id=transfer.pk, actor=asset_manager)
    transfer.refresh_from_db()
    transfer.asset.refresh_from_db()
    assert transfer.status == TransferStatus.APPROVED
    assert transfer.asset.department_id == transfer.from_department_id

    completed = complete_transfer(transfer_id=transfer.pk, actor=asset_manager)
    completed.notes = "edited"
    with pytest.raises(ValidationError, match="immutable"):
        completed.save()


@pytest.mark.django_db(transaction=True)
def test_concurrent_assignment_attempts_create_exactly_one_active_record(
    asset_manager, asset_factory, employee
):
    from accounts.models import User

    asset = asset_factory()
    barrier = Barrier(2)

    def assign():
        close_old_connections()
        try:
            actor = User.objects.get(pk=asset_manager.pk)
            assignee = User.objects.get(pk=employee.pk)
            barrier.wait(timeout=10)
            try:
                assign_asset(asset_id=asset.pk, actor=actor, assigned_to=assignee)
                return "assigned"
            except ValidationError:
                return "rejected"
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = [
            future.result(timeout=30)
            for future in (executor.submit(assign), executor.submit(assign))
        ]
    assert sorted(outcomes) == ["assigned", "rejected"]
    assert AssetAssignment.objects.filter(asset=asset, returned_at__isnull=True).count() == 1
