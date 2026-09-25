"""Asset master data and the accounting policy captured for each asset."""

import uuid

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q


class DepreciationMethod(models.TextChoices):
    SLM = "SLM", "Straight Line Method"
    RBM = "RBM", "Reducing Balance Method"
    UOP = "UOP", "Units of Production"
    SYD = "SYD", "Sum of Years' Digits"


class AssetStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    PENDING_CAPITALIZATION = "PENDING_CAPITALIZATION", "Pending Capitalization"
    ACTIVE = "ACTIVE", "Active"
    IN_MAINTENANCE = "IN_MAINTENANCE", "In Maintenance"
    TRANSFERRED = "TRANSFERRED", "Transferred"
    IMPAIRED = "IMPAIRED", "Impaired"
    DISPOSED = "DISPOSED", "Disposed"


class AssetCategory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="asset_categories",
    )
    name = models.CharField(max_length=160)
    code = models.CharField(max_length=32)
    description = models.TextField(blank=True)
    default_useful_life_months = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    default_depreciation_method = models.CharField(
        max_length=3,
        choices=DepreciationMethod.choices,
        default=DepreciationMethod.SLM,
    )
    capitalization_threshold = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "code"), name="uniq_asset_category_code_per_org"
            ),
            models.UniqueConstraint(
                fields=("organization", "name"), name="uniq_asset_category_name_per_org"
            ),
            models.CheckConstraint(
                condition=Q(default_useful_life_months__gt=0),
                name="asset_category_life_positive",
            ),
            models.CheckConstraint(
                condition=Q(capitalization_threshold__gte=0),
                name="asset_category_threshold_nonnegative",
            ),
        ]
        indexes = [
            models.Index(fields=("organization", "is_active"), name="asset_cat_org_active_idx")
        ]

    def clean(self):
        super().clean()
        self.code = self.code.strip().upper()
        self.name = self.name.strip()
        if not self.code:
            raise ValidationError({"code": "Category code cannot be blank."})
        if not self.name:
            raise ValidationError({"name": "Category name cannot be blank."})

    def __str__(self):
        return f"{self.code} - {self.name}"


class Asset(models.Model):
    """Fixed asset master record.

    Purchase cost, residual value, useful life, and depreciation method capture
    the approved asset policy. Accumulated depreciation is maintained by future
    posting services; current book value is a query-friendly snapshot maintained
    alongside those postings, not an independent accounting source of truth.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="assets"
    )
    asset_tag = models.CharField(max_length=64)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.ForeignKey(AssetCategory, on_delete=models.PROTECT, related_name="assets")
    serial_number = models.CharField(max_length=128, blank=True)
    model_number = models.CharField(max_length=128, blank=True)
    manufacturer = models.CharField(max_length=160, blank=True)
    department = models.ForeignKey(
        "organizations.Department",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="assets",
    )
    location = models.ForeignKey(
        "organizations.Location",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="assets",
    )
    status = models.CharField(max_length=32, choices=AssetStatus.choices, default=AssetStatus.DRAFT)
    acquisition_date = models.DateField(null=True, blank=True)
    capitalization_date = models.DateField(null=True, blank=True)
    purchase_cost = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    residual_value = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    useful_life_months = models.PositiveIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1)]
    )
    depreciation_method = models.CharField(
        max_length=3,
        choices=DepreciationMethod.choices,
        default=DepreciationMethod.SLM,
    )
    accumulated_depreciation = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    current_book_value = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_assets",
    )
    updated_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_assets",
    )

    class Meta:
        ordering = ("asset_tag",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "asset_tag"), name="uniq_asset_tag_per_org"
            ),
            models.CheckConstraint(condition=~Q(asset_tag=""), name="asset_tag_not_blank"),
            models.CheckConstraint(
                condition=Q(purchase_cost__gte=0), name="asset_purchase_cost_nonnegative"
            ),
            models.CheckConstraint(
                condition=Q(residual_value__gte=0), name="asset_residual_nonnegative"
            ),
            models.CheckConstraint(
                condition=Q(residual_value__lte=F("purchase_cost")),
                name="asset_residual_lte_cost",
            ),
            models.CheckConstraint(
                condition=Q(useful_life_months__isnull=True) | Q(useful_life_months__gt=0),
                name="asset_life_positive_if_set",
            ),
            models.CheckConstraint(
                condition=Q(current_book_value__gte=0), name="asset_book_value_nonnegative"
            ),
            models.CheckConstraint(
                condition=Q(accumulated_depreciation__gte=0),
                name="asset_accum_depr_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(capitalization_date__isnull=True)
                | Q(acquisition_date__isnull=True)
                | Q(capitalization_date__gte=F("acquisition_date")),
                name="asset_capitalization_not_before_acquisition",
            ),
        ]
        indexes = [
            models.Index(fields=("organization", "status"), name="asset_org_status_idx"),
            models.Index(fields=("organization", "category"), name="asset_org_category_idx"),
            models.Index(fields=("organization", "department"), name="asset_org_dept_idx"),
            models.Index(fields=("organization", "location"), name="asset_org_location_idx"),
            models.Index(
                fields=("organization", "acquisition_date"), name="asset_org_acq_date_idx"
            ),
            models.Index(fields=("organization", "manufacturer"), name="asset_org_mfr_idx"),
            models.Index(fields=("organization", "serial_number"), name="asset_org_serial_idx"),
        ]

    def clean(self):
        super().clean()
        self.asset_tag = self.asset_tag.strip()
        if not self.asset_tag:
            raise ValidationError({"asset_tag": "Asset tag cannot be blank."})

        errors = {}
        if self.residual_value > self.purchase_cost:
            errors["residual_value"] = "Residual value cannot exceed purchase cost."
        if self.acquisition_date and self.capitalization_date:
            if self.capitalization_date < self.acquisition_date:
                errors["capitalization_date"] = (
                    "Capitalization date cannot precede acquisition date."
                )

        for field_name in ("category", "department", "location"):
            relation = getattr(self, field_name, None)
            if relation and relation.organization_id != self.organization_id:
                errors[field_name] = f"The {field_name} must belong to the asset's organization."

        for field_name in ("created_by", "updated_by"):
            user = getattr(self, field_name, None)
            if user and user.organization_id not in (None, self.organization_id):
                errors[field_name] = (
                    f"The {field_name.replace('_', ' ')} must belong to the asset's organization."
                )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.asset_tag} - {self.name}"
