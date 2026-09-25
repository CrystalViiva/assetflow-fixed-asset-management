"""Transactional acquisition and capitalization domain operations."""

from datetime import date, datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from assets.models import Acquisition, AcquisitionStatus, Asset, AssetStatus
from audit.services import record_event

ACQUISITION_FIELDS = {
    "vendor_name",
    "invoice_number",
    "acquisition_date",
    "capitalization_date",
    "currency",
    "purchase_price",
    "freight_cost",
    "installation_cost",
    "civil_works_cost",
    "other_capitalizable_cost",
    "reference",
    "notes",
}


def _actor_organization(actor):
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


def _changes(before, after):
    return {
        field: {"from": _audit_value(before[field]), "to": _audit_value(value)}
        for field, value in after.items()
        if before[field] != value
    }


def _translate_duplicate_asset(exc):
    cause = exc.__cause__
    diagnostic = getattr(cause, "diag", None)
    if getattr(diagnostic, "constraint_name", None) == "assets_acquisition_asset_id_key":
        raise ValidationError(
            {"asset": "An acquisition record already exists for this asset."}
        ) from exc
    raise exc


def calculate_capitalized_cost(
    *,
    purchase_price,
    freight_cost=Decimal("0.00"),
    installation_cost=Decimal("0.00"),
    civil_works_cost=Decimal("0.00"),
    other_capitalizable_cost=Decimal("0.00"),
):
    """Return the exact Decimal sum of directly attributable cost components."""
    return sum(
        (
            purchase_price,
            freight_cost,
            installation_cost,
            civil_works_cost,
            other_capitalizable_cost,
        ),
        Decimal("0.00"),
    )


def create_acquisition(*, actor, data, ip_address=None):
    """Create an acquisition record and audit it in the same transaction."""
    organization = _actor_organization(actor)
    values = dict(data)
    asset = values.pop("asset", None)
    if asset is None:
        raise ValidationError({"asset": "An asset is required."})
    unsupported_fields = set(values) - ACQUISITION_FIELDS
    if unsupported_fields:
        raise ValidationError(
            {
                field: "This field is controlled by the acquisition workflow."
                for field in unsupported_fields
            }
        )
    values.setdefault("currency", organization.currency)

    try:
        with transaction.atomic():
            try:
                asset = (
                    Asset.objects.select_for_update(of=("self",))
                    .select_related("organization")
                    .get(pk=asset.pk, organization=organization)
                )
            except Asset.DoesNotExist as exc:
                raise ValidationError(
                    {"asset": "The asset must belong to your organization."}
                ) from exc
            if asset.status not in (AssetStatus.DRAFT, AssetStatus.PENDING_CAPITALIZATION):
                raise ValidationError(
                    {"asset": "Only draft assets can receive an acquisition record."}
                )
            if asset.acquisition_date and values.get("acquisition_date") != asset.acquisition_date:
                raise ValidationError(
                    {"acquisition_date": "Acquisition date must match the asset's recorded date."}
                )

            acquisition = Acquisition(
                organization=organization,
                asset=asset,
                created_by=actor,
                updated_by=actor,
                **values,
            )
            acquisition.full_clean()
            acquisition.save()
            record_event(
                organization=organization,
                user=actor,
                action="ACQUISITION_CREATED",
                entity_type="ACQUISITION",
                entity_id=acquisition.pk,
                ip_address=ip_address,
                changes={
                    "asset": {"from": None, "to": str(asset.pk)},
                    "total_cost": {"from": None, "to": str(acquisition.total_cost)},
                    "status": {"from": None, "to": acquisition.status},
                },
                metadata={"invoice_number": acquisition.invoice_number},
            )
    except IntegrityError as exc:
        _translate_duplicate_asset(exc)
    return acquisition


def update_acquisition(*, acquisition_id, actor, data, ip_address=None):
    """Update a draft acquisition's source data and append a material audit event."""
    organization = _actor_organization(actor)
    values = dict(data)
    unsupported_fields = set(values) - ACQUISITION_FIELDS
    if unsupported_fields:
        raise ValidationError(
            {
                field: "This field is controlled by the acquisition workflow."
                for field in unsupported_fields
            }
        )

    with transaction.atomic():
        try:
            acquisition = (
                Acquisition.objects.select_for_update(of=("self",))
                .select_related("asset", "organization")
                .get(pk=acquisition_id, organization=organization)
            )
        except Acquisition.DoesNotExist as exc:
            raise ValidationError(
                {"acquisition": "The acquisition was not found in your organization."}
            ) from exc
        if acquisition.status != AcquisitionStatus.DRAFT:
            raise ValidationError({"status": "Only draft acquisitions can be updated."})

        try:
            acquisition.asset = (
                Asset.objects.select_for_update(of=("self",))
                .select_related("organization")
                .get(pk=acquisition.asset_id, organization=organization)
            )
        except Asset.DoesNotExist as exc:
            raise ValidationError({"asset": "The asset must belong to your organization."}) from exc

        before = {field: getattr(acquisition, field) for field in values}
        before["total_cost"] = acquisition.total_cost
        for field, value in values.items():
            setattr(acquisition, field, value)
        acquisition.updated_by = actor
        acquisition.full_clean()
        changes = _changes(before, {**values, "total_cost": acquisition.total_cost})
        if not changes:
            return acquisition

        acquisition.save()
        record_event(
            organization=organization,
            user=actor,
            action="ACQUISITION_UPDATED",
            entity_type="ACQUISITION",
            entity_id=acquisition.pk,
            ip_address=ip_address,
            changes=changes,
            metadata={"asset_id": str(acquisition.asset_id)},
        )
    return acquisition


def capitalize_acquisition(*, acquisition_id, actor, ip_address=None):
    """Capitalize exactly once, locking both acquisition and asset rows."""
    organization = _actor_organization(actor)

    with transaction.atomic():
        try:
            acquisition = (
                Acquisition.objects.select_for_update(of=("self",))
                .select_related("asset", "organization")
                .get(pk=acquisition_id, organization=organization)
            )
        except Acquisition.DoesNotExist as exc:
            raise ValidationError(
                {"acquisition": "The acquisition was not found in your organization."}
            ) from exc

        if acquisition.status != AcquisitionStatus.DRAFT:
            raise ValidationError({"status": "This acquisition has already been capitalized."})
        if not acquisition.capitalization_date:
            raise ValidationError({"capitalization_date": "A capitalization date is required."})

        try:
            asset = (
                Asset.objects.select_for_update(of=("self",))
                .select_related("category")
                .get(pk=acquisition.asset_id, organization=organization)
            )
        except Asset.DoesNotExist as exc:
            raise ValidationError({"asset": "The asset must belong to your organization."}) from exc

        if asset.status not in (AssetStatus.DRAFT, AssetStatus.PENDING_CAPITALIZATION):
            raise ValidationError({"asset": "Only a draft asset can be capitalized."})
        if (
            asset.capitalization_date
            and asset.capitalization_date != acquisition.capitalization_date
        ):
            raise ValidationError(
                {"capitalization_date": "The asset's recorded date conflicts with the acquisition."}
            )
        if asset.current_book_value != Decimal("0.00") or asset.accumulated_depreciation != Decimal(
            "0.00"
        ):
            raise ValidationError({"asset": "The asset already has an accounting balance."})
        if asset.acquisition_date and asset.acquisition_date != acquisition.acquisition_date:
            raise ValidationError(
                {"acquisition_date": "Acquisition date must match the asset's recorded date."}
            )

        capitalized_cost = acquisition.calculate_capitalized_cost()
        if capitalized_cost <= 0:
            raise ValidationError({"total_cost": "Capitalized cost must be greater than zero."})
        if asset.residual_value > capitalized_cost:
            raise ValidationError(
                {"residual_value": "Residual value cannot exceed capitalized cost."}
            )
        before_asset = {
            "status": asset.status,
            "purchase_cost": asset.purchase_cost,
            "current_book_value": asset.current_book_value,
            "acquisition_date": asset.acquisition_date,
            "capitalization_date": asset.capitalization_date,
            "useful_life_months": asset.useful_life_months,
        }
        before_acquisition_status = acquisition.status

        if asset.useful_life_months is None:
            asset.useful_life_months = asset.category.default_useful_life_months
        if acquisition.currency != organization.currency.strip().upper():
            raise ValidationError(
                {"currency": "Acquisition currency must match the organization's base currency."}
            )

        asset.purchase_cost = capitalized_cost
        asset.current_book_value = capitalized_cost
        asset.acquisition_date = acquisition.acquisition_date
        asset.capitalization_date = acquisition.capitalization_date
        asset.status = AssetStatus.ACTIVE
        asset.updated_by = actor
        asset.full_clean()

        acquisition.status = AcquisitionStatus.CAPITALIZED
        acquisition.updated_by = actor
        acquisition.full_clean()

        asset.save(
            update_fields=(
                "purchase_cost",
                "current_book_value",
                "acquisition_date",
                "capitalization_date",
                "useful_life_months",
                "status",
                "updated_by",
                "updated_at",
            )
        )
        acquisition.save()

        asset_changes = {
            field: {
                "from": _audit_value(before_asset[field]),
                "to": _audit_value(getattr(asset, field)),
            }
            for field in before_asset
            if before_asset[field] != getattr(asset, field)
        }
        acquisition_changes = {
            "status": {
                "from": before_acquisition_status,
                "to": acquisition.status,
            },
            "capitalized_cost": {"from": None, "to": str(capitalized_cost)},
        }
        metadata = {
            "asset_id": str(asset.pk),
            "acquisition_id": str(acquisition.pk),
            "currency": acquisition.currency,
            "invoice_number": acquisition.invoice_number,
        }
        record_event(
            organization=organization,
            user=actor,
            action="ASSET_CAPITALIZED",
            entity_type="ASSET",
            entity_id=asset.pk,
            ip_address=ip_address,
            changes=asset_changes,
            metadata=metadata,
        )
        record_event(
            organization=organization,
            user=actor,
            action="ACQUISITION_CAPITALIZED",
            entity_type="ACQUISITION",
            entity_id=acquisition.pk,
            ip_address=ip_address,
            changes=acquisition_changes,
            metadata=metadata,
        )

    return acquisition
