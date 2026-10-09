"""Narrow tenant user administration API. Django enforces every permission."""

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Q
from rest_framework import serializers
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated

from accounts.models import User, UserRole
from audit.services import record_event
from common.pagination import StandardResultsPagination
from organizations.models import Department, Organization


class TenantAdminPermission(IsAuthenticated):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        user = request.user
        return bool(
            user.is_active
            and user.organization_id
            and user.role == UserRole.ADMIN
            and not user.is_superuser
            and not user.is_platform_operator
        )


class UserAdminSerializer(serializers.ModelSerializer):
    department_id = serializers.UUIDField(required=False, allow_null=True)
    department_name = serializers.CharField(
        source="department.name", read_only=True, allow_null=True
    )
    password = serializers.CharField(
        write_only=True, required=False, trim_whitespace=False, style={"input_type": "password"}
    )

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "role",
            "department_id",
            "department_name",
            "is_active",
            "created_at",
            "last_login",
            "password",
        )
        read_only_fields = ("id", "department_name", "created_at", "last_login")

    def get_fields(self):
        fields = super().get_fields()
        fields["password"].required = self.instance is None
        return fields

    def to_internal_value(self, data):
        if isinstance(data, dict):
            allowed = {"role", "department_id", "is_active"} | (
                {"email", "password"} if self.instance is None else set()
            )
            unknown = set(data) - allowed
            if unknown:
                raise serializers.ValidationError(
                    {key: "This field is not supported." for key in sorted(unknown)}
                )
        return super().to_internal_value(data)

    def validate_email(self, value):
        value = User.objects.normalize_email(value).strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_role(self, value):
        if value not in UserRole.values:
            raise serializers.ValidationError("Select a supported organization role.")
        return value

    def validate_department_id(self, value):
        if value is None:
            return None
        try:
            department = Department.objects.get(
                pk=value, organization_id=self.context["request"].user.organization_id
            )
        except Department.DoesNotExist:
            raise serializers.ValidationError("Choose a department in this organization.") from None
        if not department.is_active and (
            self.instance is None or self.instance.department_id != department.pk
        ):
            raise serializers.ValidationError("Choose an active department in this organization.")
        return department

    def validate_password(self, value):
        try:
            candidate = User(email=self.initial_data.get("email", ""))
            validate_password(value, user=candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value

    def validate(self, attrs):
        if self.instance is None and not attrs.get("password"):
            raise serializers.ValidationError({"password": "An initial password is required."})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        department = validated_data.pop("department_id", None)
        user = User(
            email=validated_data.pop("email"),
            organization=self.context["request"].user.organization,
            department=department,
            **validated_data,
        )
        user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        department = validated_data.pop("department_id", serializers.empty)
        if department is not serializers.empty:
            instance.department = department
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance


class UserAdminList(ListCreateAPIView):
    permission_classes = (TenantAdminPermission,)
    serializer_class = UserAdminSerializer
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        queryset = User.objects.filter(
            organization_id=self.request.user.organization_id
        ).select_related("department")
        search = self.request.query_params.get("search", "").strip()
        if len(search) > 200:
            raise serializers.ValidationError({"search": "Keep search to 200 characters or fewer."})
        if search:
            queryset = queryset.filter(
                Q(email__icontains=search) | Q(department__name__icontains=search)
            )
        role = self.request.query_params.get("role")
        if role:
            if role not in UserRole.values:
                raise serializers.ValidationError({"role": "Select a supported organization role."})
            queryset = queryset.filter(role=role)
        department = self.request.query_params.get("department")
        if department:
            queryset = queryset.filter(department_id=department)
        active = self.request.query_params.get("is_active")
        if active in {"true", "false"}:
            queryset = queryset.filter(is_active=active == "true")
        return queryset.order_by("email", "id")

    @transaction.atomic
    def perform_create(self, serializer):
        from commercial.entitlements import require_capacity

        require_capacity(self.request.user.organization, "active_users")
        department = serializer.validated_data.get("department_id")
        if department is not None:
            try:
                serializer.validated_data["department_id"] = (
                    Department.objects.select_for_update().get(
                        pk=department.pk,
                        organization_id=self.request.user.organization_id,
                        is_active=True,
                    )
                )
            except Department.DoesNotExist:
                raise serializers.ValidationError(
                    {"department_id": "Choose an active department in this organization."}
                ) from None
        target = serializer.save()
        record_event(
            organization=self.request.user.organization,
            user=self.request.user,
            action="USER_CREATED",
            entity_type="USER",
            entity_id=target.id,
            ip_address=self.request.META.get("REMOTE_ADDR"),
            changes={
                "email": {"old": None, "new": target.email},
                "role": {"old": None, "new": target.role},
                "department_id": {
                    "old": None,
                    "new": str(target.department_id) if target.department_id else None,
                },
            },
        )


class UserAdminDetail(RetrieveUpdateAPIView):
    permission_classes = (TenantAdminPermission,)
    serializer_class = UserAdminSerializer
    lookup_field = "id"
    http_method_names = ("get", "patch", "head", "options")

    def get_queryset(self):
        return User.objects.filter(
            organization_id=self.request.user.organization_id
        ).select_related("department")

    @transaction.atomic
    def perform_update(self, serializer):
        Organization.objects.select_for_update().get(pk=self.request.user.organization_id)
        target = User.objects.select_for_update().get(
            pk=serializer.instance.pk, organization_id=self.request.user.organization_id
        )
        serializer.instance = target
        if target.pk == self.request.user.pk:
            raise serializers.ValidationError(
                "Administrators cannot change their own role, department, or active state."
            )
        before = {
            "role": target.role,
            "department_id": target.department_id,
            "is_active": target.is_active,
        }
        values = serializer.validated_data
        department = values.get("department_id", serializers.empty)
        if department is not serializers.empty and department is not None:
            try:
                department = Department.objects.select_for_update().get(
                    pk=department.pk,
                    organization_id=target.organization_id,
                )
            except Department.DoesNotExist:
                raise serializers.ValidationError(
                    {"department_id": "Choose a department in this organization."}
                ) from None
            if not department.is_active and target.department_id != department.pk:
                raise serializers.ValidationError(
                    {"department_id": "Choose an active department in this organization."}
                )
            values["department_id"] = department
        next_role = values.get("role", target.role)
        next_active = values.get("is_active", target.is_active)
        if next_active and not target.is_active:
            from commercial.entitlements import require_capacity

            require_capacity(self.request.user.organization, "active_users")
        if not next_active and target.is_active:
            target.session_version += 1
        if (
            target.role == UserRole.ADMIN
            and target.is_active
            and (next_role != UserRole.ADMIN or not next_active)
        ):
            admins = User.objects.select_for_update().filter(
                organization_id=target.organization_id, role=UserRole.ADMIN, is_active=True
            )
            if admins.count() <= 1:
                raise serializers.ValidationError(
                    "The organization must retain at least one active administrator."
                )
        target = serializer.save()
        after = {
            "role": target.role,
            "department_id": target.department_id,
            "is_active": target.is_active,
        }
        changes = {
            key: {
                "old": str(before[key]) if key == "department_id" and before[key] else before[key],
                "new": str(after[key]) if key == "department_id" and after[key] else after[key],
            }
            for key in before
            if before[key] != after[key]
        }
        if changes:
            record_event(
                organization=self.request.user.organization,
                user=self.request.user,
                action="USER_ADMIN_UPDATED",
                entity_type="USER",
                entity_id=target.id,
                ip_address=self.request.META.get("REMOTE_ADDR"),
                changes=changes,
            )
