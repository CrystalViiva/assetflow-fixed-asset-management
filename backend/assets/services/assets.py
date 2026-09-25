"""Transactional Asset master-data operations."""

from datetime import date, datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from assets.models import Asset
from assets.services.validation import validate_organization_relationships
from audit.services import record_event

ASSET_MASTER_FIELDS = {
    "asset_tag",
    "name",
    "description",
    "category",
    "serial_number",
    "model_number",
    "manufacturer",
    "department",
    "location",
    "acquisition_date",
    "capitalization_date",
    "purchase_cost",
    "residual_value",
    "useful_life_months",
    "depreciation_method",
}


def _require_actor_organization(actor):
    organization = getattr(actor, "organization", None)
    if organization is None:
        raise ValidationError(
            {"organization": "The authenticated user must belong to an organization."}
        )
    return organization


def _audit_value(value):
    if hasattr(value, "_meta"):
        return str(value.pk)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def _capture_changes(original_values, submitted_data):
    changes = {}
    for field_name, new_value in submitted_data.items():
        old_value = original_values[field_name]
        if old_value != new_value:
            changes[field_name] = {
                "from": _audit_value(old_value),
                "to": _audit_value(new_value),
            }
    return changes


def _raise_tag_conflict(exc):
    database_error = exc.__cause__
    diagnostic = getattr(database_error, "diag", None)
    if getattr(diagnostic, "constraint_name", None) == "uniq_asset_tag_per_org":
        raise ValidationError(
            {"asset_tag": "This asset tag is already used in the organization."}
        ) from exc
    raise exc


def create_asset(*, actor, data, ip_address=None):
    """Validate, persist, and audit a new asset as one database transaction."""
    organization = _require_actor_organization(actor)
    asset_data = dict(data)
    unsupported_fields = set(asset_data) - ASSET_MASTER_FIELDS
    if unsupported_fields:
        raise ValidationError(
            {
                field: "This field is managed by an asset lifecycle service."
                for field in unsupported_fields
            }
        )
    category = asset_data.get("category")
    if category is None:
        raise ValidationError({"category": "An asset category is required."})

    validate_organization_relationships(
        organization=organization,
        category=category,
        department=asset_data.get("department"),
        location=asset_data.get("location"),
    )

    if "useful_life_months" not in asset_data:
        asset_data["useful_life_months"] = category.default_useful_life_months
    if "depreciation_method" not in asset_data:
        asset_data["depreciation_method"] = category.default_depreciation_method

    asset_data["asset_tag"] = asset_data.get("asset_tag", "").strip()
    asset = Asset(
        organization=organization,
        created_by=actor,
        updated_by=actor,
        **asset_data,
    )

    try:
        with transaction.atomic():
            asset.full_clean()
            asset.save()
            record_event(
                organization=organization,
                user=actor,
                action="ASSET_CREATED",
                entity_type="ASSET",
                entity_id=asset.pk,
                ip_address=ip_address,
                changes={
                    "asset_tag": {"from": None, "to": asset.asset_tag},
                    "name": {"from": None, "to": asset.name},
                    "status": {"from": None, "to": asset.status},
                },
                metadata={"source": "asset_master_data"},
            )
    except IntegrityError as exc:
        _raise_tag_conflict(exc)
    return asset


def update_asset(*, asset_id, actor, data, ip_address=None):
    """Apply editable master-data changes and append an audit event atomically."""
    organization = _require_actor_organization(actor)
    submitted_data = dict(data)
    unsupported_fields = set(submitted_data) - ASSET_MASTER_FIELDS
    if unsupported_fields:
        raise ValidationError(
            {
                field: "This field is managed by an asset lifecycle service."
                for field in unsupported_fields
            }
        )
    if "asset_tag" in submitted_data:
        submitted_data["asset_tag"] = submitted_data["asset_tag"].strip()

    try:
        with transaction.atomic():
            try:
                asset = (
                    Asset.objects.select_for_update(of=("self",))
                    .select_related("category", "department", "location", "organization")
                    .get(pk=asset_id, organization=organization)
                )
            except Asset.DoesNotExist as exc:
                raise ValidationError(
                    {"asset": "The asset was not found in your organization."}
                ) from exc

            original_values = {
                field_name: getattr(asset, field_name) for field_name in submitted_data
            }
            for field_name, value in submitted_data.items():
                setattr(asset, field_name, value)

            validate_organization_relationships(
                organization=organization,
                category=asset.category,
                department=asset.department,
                location=asset.location,
            )
            asset.updated_by = actor
            asset.full_clean()
            changes = _capture_changes(original_values, submitted_data)
            if not changes:
                return asset

            asset.save()
            record_event(
                organization=organization,
                user=actor,
                action="ASSET_UPDATED",
                entity_type="ASSET",
                entity_id=asset.pk,
                ip_address=ip_address,
                changes=changes,
                metadata={"source": "asset_master_data"},
            )
    except IntegrityError as exc:
        _raise_tag_conflict(exc)
    return asset
