from rest_framework import serializers

from assets.models import Acquisition, Asset, AssetCategory, CurrencyCode
from organizations.models import Department, Location


class AcquisitionSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    asset_id = serializers.PrimaryKeyRelatedField(
        source="asset", queryset=Asset.objects.none(), required=True
    )
    asset_tag = serializers.CharField(source="asset.asset_tag", read_only=True)
    asset_name = serializers.CharField(source="asset.name", read_only=True)
    total_cost = serializers.DecimalField(max_digits=20, decimal_places=2, read_only=True)
    currency = serializers.ChoiceField(choices=CurrencyCode.choices, required=False)

    class Meta:
        model = Acquisition
        fields = (
            "id",
            "organization_id",
            "asset_id",
            "asset_tag",
            "asset_name",
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
            "total_cost",
            "reference",
            "notes",
            "status",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "organization_id",
            "asset_tag",
            "asset_name",
            "total_cost",
            "status",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        )

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        organization_id = getattr(getattr(request, "user", None), "organization_id", None)
        fields["asset_id"].queryset = Asset.objects.filter(organization_id=organization_id)
        if self.instance is not None:
            fields["asset_id"].read_only = True
        return fields


class AssetCategorySerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)

    class Meta:
        model = AssetCategory
        fields = (
            "id",
            "organization_id",
            "organization_name",
            "name",
            "code",
            "description",
            "default_useful_life_months",
            "default_depreciation_method",
            "capitalization_threshold",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "organization_id",
            "organization_name",
            "created_at",
            "updated_at",
        )

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Category name cannot be blank.")
        return value

    def validate_code(self, value):
        value = value.strip().upper()
        if not value:
            raise serializers.ValidationError("Category code cannot be blank.")
        return value

    def validate(self, attrs):
        request = self.context.get("request")
        organization_id = getattr(
            self.instance,
            "organization_id",
            getattr(getattr(request, "user", None), "organization_id", None),
        )
        name = attrs.get("name", getattr(self.instance, "name", None))
        code = attrs.get("code", getattr(self.instance, "code", None))
        categories = AssetCategory.objects.filter(organization_id=organization_id)
        if self.instance:
            categories = categories.exclude(pk=self.instance.pk)
        errors = {}
        if name and categories.filter(name__iexact=name).exists():
            errors["name"] = "A category with this name already exists in the organization."
        if code and categories.filter(code__iexact=code).exists():
            errors["code"] = "A category with this code already exists in the organization."
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class AssetSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        source="category", queryset=AssetCategory.objects.none()
    )
    category_name = serializers.CharField(source="category.name", read_only=True)
    category_code = serializers.CharField(source="category.code", read_only=True)
    department_id = serializers.PrimaryKeyRelatedField(
        source="department",
        queryset=Department.objects.none(),
        required=False,
        allow_null=True,
    )
    department_name = serializers.CharField(
        source="department.name", read_only=True, allow_null=True
    )
    department_code = serializers.CharField(
        source="department.code", read_only=True, allow_null=True
    )
    location_id = serializers.PrimaryKeyRelatedField(
        source="location",
        queryset=Location.objects.none(),
        required=False,
        allow_null=True,
    )
    location_name = serializers.CharField(source="location.name", read_only=True, allow_null=True)
    location_code = serializers.CharField(source="location.code", read_only=True, allow_null=True)
    created_by_email = serializers.CharField(
        source="created_by.email", read_only=True, allow_null=True
    )
    updated_by_email = serializers.CharField(
        source="updated_by.email", read_only=True, allow_null=True
    )

    class Meta:
        model = Asset
        fields = (
            "id",
            "organization_id",
            "organization_name",
            "asset_tag",
            "name",
            "description",
            "category_id",
            "category_name",
            "category_code",
            "serial_number",
            "model_number",
            "manufacturer",
            "department_id",
            "department_name",
            "department_code",
            "location_id",
            "location_name",
            "location_code",
            "status",
            "acquisition_date",
            "capitalization_date",
            "available_for_use_date",
            "purchase_cost",
            "residual_value",
            "useful_life_months",
            "depreciation_method",
            "accumulated_depreciation",
            "current_book_value",
            "created_at",
            "updated_at",
            "created_by_email",
            "updated_by_email",
        )
        read_only_fields = (
            "id",
            "organization_id",
            "organization_name",
            "category_name",
            "category_code",
            "department_name",
            "department_code",
            "location_name",
            "location_code",
            "status",
            "accumulated_depreciation",
            "current_book_value",
            "created_at",
            "updated_at",
            "created_by_email",
            "updated_by_email",
        )

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        organization_id = getattr(getattr(request, "user", None), "organization_id", None)
        fields["category_id"].queryset = AssetCategory.objects.filter(
            organization_id=organization_id
        )
        fields["department_id"].queryset = Department.objects.filter(
            organization_id=organization_id
        )
        fields["location_id"].queryset = Location.objects.filter(organization_id=organization_id)
        return fields

    def validate_asset_tag(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Asset tag cannot be blank.")
        return value
