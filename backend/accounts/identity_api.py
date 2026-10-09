"""Narrow public identity endpoints and scoped administration."""

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from accounts.admin_api import TenantAdminPermission
from accounts.identity_services import (
    GENERIC_RESPONSE,
    accept_ticket,
    audit,
    invite,
    issue_ticket,
    password_check,
    provision,
    require_operator,
)
from accounts.models import IdentityTicket, User, UserRole
from accounts.throttles import IdentityThrottle, RefreshThrottle
from organizations.models import Organization


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if isinstance(data, dict) and set(data) - set(self.fields):
            raise serializers.ValidationError(
                {"non_field_errors": ["Unsupported fields were supplied."]}
            )
        return super().to_internal_value(data)


class EmailInput(StrictSerializer):
    email = serializers.EmailField(max_length=254)

    def validate_email(self, value):
        return value.strip().lower()


class InvitationInput(EmailInput):
    role = serializers.ChoiceField(choices=UserRole.choices)
    department_id = serializers.UUIDField(required=False, allow_null=True)


class CompletionInput(StrictSerializer):
    token = serializers.CharField(max_length=1024)
    password = serializers.CharField(max_length=256, trim_whitespace=False, write_only=True)


class ProvisionInput(EmailInput):
    key = serializers.UUIDField()
    name = serializers.CharField(max_length=160)
    code = serializers.RegexField(r"^[A-Za-z0-9_-]{2,32}$")
    currency = serializers.CharField(max_length=3, default="NGN")
    timezone_name = serializers.CharField(max_length=64, default="Africa/Lagos")


def validated(serializer_type, request):
    serializer = serializer_type(data=request.data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def ensure_session(user, token):
    if (
        not user.is_active
        or (user.organization_id and not user.organization.is_active)
        or token.get("session_version", 0) != user.session_version
    ):
        raise AuthenticationFailed("This session has ended. Sign in again.")


class SessionTokenSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["session_version"] = user.session_version
        return token

    def validate(self, attrs):
        attrs["email"] = attrs["email"].strip().lower()
        data = super().validate(attrs)
        ensure_session(self.user, {"session_version": self.user.session_version})
        return data


class SessionRefreshSerializer(TokenRefreshSerializer):
    @transaction.atomic
    def validate(self, attrs):
        token = RefreshToken(attrs["refresh"])
        user = get_object_or_404(User.objects.select_for_update(), pk=token["user_id"])
        ensure_session(user, token)
        # Revalidate blacklist under the user lock so concurrent rotation cannot both win.
        return super().validate(attrs)


class LoginView(TokenObtainPairView):
    serializer_class = SessionTokenSerializer
    throttle_classes = [IdentityThrottle]


class RefreshView(TokenRefreshView):
    serializer_class = SessionRefreshSerializer
    throttle_classes = [RefreshThrottle]


class PublicIdentityView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [IdentityThrottle]


class ResetRequest(PublicIdentityView):
    @extend_schema(request=EmailInput, responses={202: OpenApiTypes.OBJECT})
    @transaction.atomic
    def post(self, request):
        email = validated(EmailInput, request)["email"]
        candidate = User.objects.filter(email=email, is_active=True).first()
        if candidate and candidate.organization_id:
            Organization.objects.select_for_update().get(pk=candidate.organization_id)
        user = User.objects.select_for_update().filter(email=email, is_active=True).first()
        if user and (not user.organization_id or user.organization.is_active):
            issue_ticket(purpose="RESET", email=email, user=user, organization=user.organization)
            audit(user.organization, user, "PASSWORD_RESET_REQUESTED", user.pk)
        return Response(GENERIC_RESPONSE, status=202)


class ResetComplete(PublicIdentityView):
    purpose = "RESET"

    @extend_schema(request=CompletionInput, responses=OpenApiTypes.OBJECT)
    def post(self, request):
        accept_ticket(purpose=self.purpose, **validated(CompletionInput, request))
        return Response({"detail": "Your password is set. Sign in to continue."})


class InvitationComplete(ResetComplete):
    purpose = "INVITE"


class InvitationList(APIView):
    permission_classes = [TenantAdminPermission]
    throttle_classes = [IdentityThrottle]

    @extend_schema(responses={200: {"type": "array", "items": {"type": "object"}}})
    def get(self, request):
        tickets = IdentityTicket.objects.filter(
            organization=request.user.organization, purpose="INVITE"
        ).order_by("-created_at")[:100]
        return Response(
            [
                dict(
                    id=str(t.pk),
                    email=t.email,
                    role=t.role,
                    expires_at=t.expires_at,
                    consumed_at=t.consumed_at,
                    revoked_at=t.revoked_at,
                )
                for t in tickets
            ]
        )

    @extend_schema(request=InvitationInput, responses={202: OpenApiTypes.OBJECT})
    def post(self, request):
        invite(actor=request.user, **validated(InvitationInput, request))
        return Response(GENERIC_RESPONSE, status=202)


class InvitationRevoke(APIView):
    permission_classes = [TenantAdminPermission]

    @extend_schema(request=None, responses=OpenApiTypes.OBJECT)
    @transaction.atomic
    def post(self, request, pk):
        Organization.objects.select_for_update().get(pk=request.user.organization_id)
        ticket = get_object_or_404(
            IdentityTicket.objects.select_for_update(),
            pk=pk,
            organization=request.user.organization,
            purpose="INVITE",
        )
        if not ticket.consumed_at and not ticket.revoked_at:
            ticket.revoked_at = timezone.now()
            ticket.save(update_fields=["revoked_at"])
            audit(ticket.organization, request.user, "INVITATION_REVOKED", ticket.pk)
        return Response({"detail": "Invitation revoked."})


class ProvisionView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [IdentityThrottle]

    @extend_schema(request=ProvisionInput, responses={201: OpenApiTypes.OBJECT})
    def post(self, request):
        require_operator(request.user)
        result = provision(actor=request.user, **validated(ProvisionInput, request))
        return Response(
            {
                "organization_id": str(result.organization_id),
                "request_key": str(result.key),
                "activation_pending": not result.organization.is_active,
            },
            status=201,
        )


class PasswordInput(StrictSerializer):
    current_password = serializers.CharField(max_length=256, trim_whitespace=False)
    password = serializers.CharField(max_length=256, trim_whitespace=False)


class PasswordChange(APIView):
    throttle_classes = [IdentityThrottle]

    @extend_schema(request=PasswordInput, responses=OpenApiTypes.OBJECT)
    @transaction.atomic
    def post(self, request):
        values = validated(PasswordInput, request)
        user = User.objects.select_for_update().get(pk=request.user.pk)
        if not user.check_password(values["current_password"]):
            raise serializers.ValidationError("The current password was not accepted.")
        password_check(values["password"], user)
        user.set_password(values["password"])
        user.session_version += 1
        user.save(update_fields=["password", "session_version", "updated_at"])
        audit(user.organization, user, "PASSWORD_CHANGED", user.pk)
        return Response({"detail": "Password changed. Sign in again on all devices."})


class LogoutView(APIView):
    @extend_schema(request=None, responses={204: None})
    @transaction.atomic
    def post(self, request):
        user = User.objects.select_for_update().get(pk=request.user.pk)
        user.session_version += 1
        user.save(update_fields=["session_version"])
        return Response(status=204)


class ProfileView(APIView):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        user = request.user
        org = user.organization
        return Response(
            {
                "email": user.email,
                "role": user.role,
                "department": user.department.name if user.department_id else None,
                "organization": {
                    "name": org.name,
                    "legal_name": org.legal_name,
                    "currency": org.currency,
                    "timezone": org.timezone,
                }
                if org
                else None,
                "is_platform_operator": user.is_platform_operator,
            }
        )


class ProfileInput(StrictSerializer):
    name = serializers.CharField(max_length=160)
    legal_name = serializers.CharField(max_length=240, allow_blank=True)


class OrganizationProfile(APIView):
    permission_classes = [TenantAdminPermission]

    @extend_schema(request=ProfileInput, responses=ProfileInput)
    @transaction.atomic
    def patch(self, request):
        values = validated(ProfileInput, request)
        org = Organization.objects.select_for_update().get(pk=request.user.organization_id)
        org.name, org.legal_name = values["name"], values["legal_name"]
        org.save(update_fields=["name", "legal_name", "updated_at"])
        audit(org, request.user, "ORGANIZATION_PROFILE_UPDATED", org.pk)
        return Response(values)
