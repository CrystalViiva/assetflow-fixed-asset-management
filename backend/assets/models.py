"""Asset master data and the accounting policy captured for each asset."""

import uuid
from decimal import Decimal

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


class AssetCondition(models.TextChoices):
    GOOD = "GOOD", "Good"
    FAIR = "FAIR", "Fair"
    DAMAGED = "DAMAGED", "Damaged"
    CRITICAL = "CRITICAL", "Critical"
    UNKNOWN = "UNKNOWN", "Unknown"


class AcquisitionStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    CAPITALIZED = "CAPITALIZED", "Capitalized"


class CurrencyCode(models.TextChoices):
    NGN = "NGN", "Nigerian naira"
    USD = "USD", "US dollar"
    GBP = "GBP", "Pound sterling"
    EUR = "EUR", "Euro"
    ZAR = "ZAR", "South African rand"
    GHS = "GHS", "Ghanaian cedi"
    KES = "KES", "Kenyan shilling"
    XOF = "XOF", "West African CFA franc"
    XAF = "XAF", "Central African CFA franc"
    AED = "AED", "UAE dirham"
    SAR = "SAR", "Saudi riyal"
    CAD = "CAD", "Canadian dollar"
    AUD = "AUD", "Australian dollar"
    CHF = "CHF", "Swiss franc"
    CNY = "CNY", "Chinese yuan"
    JPY = "JPY", "Japanese yen"
    INR = "INR", "Indian rupee"


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


class Acquisition(models.Model):
    """Acquisition cost components and controlled capitalization state."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="acquisitions"
    )
    asset = models.OneToOneField(
        "assets.Asset", on_delete=models.PROTECT, related_name="acquisition"
    )
    vendor_name = models.CharField(max_length=200, blank=True)
    invoice_number = models.CharField(max_length=128, blank=True)
    acquisition_date = models.DateField()
    capitalization_date = models.DateField(null=True, blank=True)
    currency = models.CharField(
        max_length=3, choices=CurrencyCode.choices, default=CurrencyCode.NGN
    )
    purchase_price = models.DecimalField(
        max_digits=20, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    freight_cost = models.DecimalField(
        max_digits=20, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    installation_cost = models.DecimalField(
        max_digits=20, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    civil_works_cost = models.DecimalField(
        max_digits=20, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    other_capitalizable_cost = models.DecimalField(
        max_digits=20, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    total_cost = models.DecimalField(max_digits=20, decimal_places=2, default=0, editable=False)
    reference = models.CharField(max_length=128, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=16, choices=AcquisitionStatus.choices, default=AcquisitionStatus.DRAFT
    )
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_acquisitions",
    )
    updated_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_acquisitions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    COST_FIELDS = (
        "purchase_price",
        "freight_cost",
        "installation_cost",
        "civil_works_cost",
        "other_capitalizable_cost",
    )

    class Meta:
        ordering = ("-acquisition_date", "-created_at")
        constraints = [
            models.CheckConstraint(
                condition=Q(purchase_price__gte=0), name="acq_purchase_nonnegative"
            ),
            models.CheckConstraint(
                condition=Q(freight_cost__gte=0), name="acq_freight_nonnegative"
            ),
            models.CheckConstraint(
                condition=Q(installation_cost__gte=0), name="acq_install_nonnegative"
            ),
            models.CheckConstraint(
                condition=Q(civil_works_cost__gte=0), name="acq_civil_nonnegative"
            ),
            models.CheckConstraint(
                condition=Q(other_capitalizable_cost__gte=0), name="acq_other_nonnegative"
            ),
            models.CheckConstraint(condition=Q(total_cost__gt=0), name="acq_total_positive"),
            models.CheckConstraint(
                condition=Q(
                    total_cost=F("purchase_price")
                    + F("freight_cost")
                    + F("installation_cost")
                    + F("civil_works_cost")
                    + F("other_capitalizable_cost")
                ),
                name="acq_total_matches_components",
            ),
            models.CheckConstraint(
                condition=Q(currency__in=CurrencyCode.values), name="acq_currency_supported"
            ),
            models.CheckConstraint(
                condition=Q(status__in=AcquisitionStatus.values), name="acq_status_supported"
            ),
            models.CheckConstraint(
                condition=Q(capitalization_date__isnull=True)
                | Q(capitalization_date__gte=F("acquisition_date")),
                name="acq_capdate_after_acqdate",
            ),
        ]
        indexes = [
            models.Index(fields=("organization", "status"), name="acq_org_status_idx"),
            models.Index(fields=("organization", "acquisition_date"), name="acq_org_acqdate_idx"),
            models.Index(
                fields=("organization", "capitalization_date"), name="acq_org_capdate_idx"
            ),
            models.Index(fields=("organization", "invoice_number"), name="acq_org_invoice_idx"),
        ]

    def calculate_capitalized_cost(self):
        """Sum monetary cost components without binary floating-point arithmetic."""
        return sum((getattr(self, field) for field in self.COST_FIELDS), Decimal("0.00"))

    def clean(self):
        super().clean()
        if isinstance(self.currency, str):
            self.currency = self.currency.strip().upper()
        self.total_cost = self.calculate_capitalized_cost()
        errors = {}
        if not self.currency:
            errors["currency"] = "A supported currency code is required."

        for field in self.COST_FIELDS:
            if getattr(self, field) < 0:
                errors[field] = "Capitalizable cost components cannot be negative."
        if self.total_cost <= 0:
            errors["total_cost"] = "Total capitalized cost must be greater than zero."
        if self.capitalization_date and self.capitalization_date < self.acquisition_date:
            errors["capitalization_date"] = "Capitalization date cannot precede acquisition date."
        if self.asset_id and self.organization_id:
            if self.asset.organization_id != self.organization_id:
                errors["asset"] = "The asset must belong to the acquisition's organization."
            elif (
                self.asset.acquisition_date and self.asset.acquisition_date != self.acquisition_date
            ):
                errors["acquisition_date"] = (
                    "Acquisition date must match the asset's recorded date."
                )
        if (
            self.organization_id
            and self.currency
            and self.currency != self.organization.currency.strip().upper()
        ):
            errors["currency"] = "Acquisition currency must match the organization's base currency."
        for field_name in ("created_by", "updated_by"):
            user = getattr(self, field_name, None)
            if user and user.organization_id not in (None, self.organization_id):
                errors[field_name] = "The user must belong to the acquisition's organization."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.total_cost = self.calculate_capitalized_cost()
        update_fields = kwargs.get("update_fields")
        if update_fields is not None and set(update_fields).intersection(self.COST_FIELDS):
            kwargs["update_fields"] = set(update_fields) | {"total_cost"}
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.invoice_number or self.reference or self.pk} - {self.asset.asset_tag}"


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
    condition = models.CharField(
        max_length=12, choices=AssetCondition.choices, default=AssetCondition.UNKNOWN
    )
    acquisition_date = models.DateField(null=True, blank=True)
    capitalization_date = models.DateField(null=True, blank=True)
    available_for_use_date = models.DateField(null=True, blank=True)
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
                condition=Q(condition__in=AssetCondition.values), name="asset_condition_valid"
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
            models.CheckConstraint(
                condition=Q(available_for_use_date__isnull=True)
                | Q(capitalization_date__isnull=True)
                | Q(available_for_use_date__gte=F("capitalization_date")),
                name="asset_available_after_capitalization",
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
        if self.capitalization_date and self.available_for_use_date:
            if self.available_for_use_date < self.capitalization_date:
                errors["available_for_use_date"] = (
                    "Available-for-use date cannot precede capitalization date."
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
