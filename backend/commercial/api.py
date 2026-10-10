from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.admin_api import TenantAdminPermission
from accounts.identity_api import (
    CompletionInput,
    EmailInput,
    PublicIdentityView,
    StrictSerializer,
    validated,
)
from accounts.identity_services import GENERIC_RESPONSE, audit, require_operator
from accounts.models import IdentityTicket, ManagedProvision, PlatformEvent, User
from accounts.throttles import IdentityThrottle
from commercial import billing
from commercial.entitlements import usage, writable
from commercial.models import (
    BillingEvent,
    Checkout,
    Plan,
    ProviderSubscription,
    SalesLead,
    Subscription,
)
from commercial.registration import request_signup, verify_signup
from organizations.models import Organization


def plan_data(plan):
    return {
        "id": str(plan.pk),
        "name": plan.name,
        "code": plan.code,
        "version": plan.version,
        "currency": plan.currency,
        "monthly_amount": str(plan.monthly_amount),
        "active_users": plan.active_users,
        "registered_assets": plan.registered_assets,
        "trial_days": plan.trial_days,
        "sandbox": plan.is_sandbox,
    }


def checkout_data(checkout):
    return {
        "id": str(checkout.pk),
        "plan_id": str(checkout.plan_id),
        "status": checkout.status,
        "amount_minor": checkout.amount_minor,
        "currency": checkout.currency,
        "provider": checkout.provider,
        "url": checkout.provider_url,
        "created_at": checkout.created_at,
    }


class PublicConfig(PublicIdentityView):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        return Response(
            {
                "self_service_enabled": settings.SELF_SERVICE_ENABLED,
                "billing_provider": settings.BILLING_PROVIDER,
                "plans": [
                    plan_data(p)
                    for p in Plan.objects.filter(is_public=True).order_by("code", "version")
                ],
            }
        )


class SignupInput(EmailInput):
    company_name = serializers.CharField(max_length=160)
    currency = serializers.CharField(max_length=3, default="NGN")
    timezone_name = serializers.CharField(max_length=64, default="Africa/Lagos")


class SignupView(PublicIdentityView):
    @extend_schema(request=SignupInput, responses={202: OpenApiTypes.OBJECT})
    def post(self, request):
        request_signup(**validated(SignupInput, request))
        return Response(GENERIC_RESPONSE, status=202)


class VerifyInput(CompletionInput):
    plan_id = serializers.UUIDField()


class VerifySignup(PublicIdentityView):
    @extend_schema(request=VerifyInput, responses=OpenApiTypes.OBJECT)
    def post(self, request):
        verify_signup(**validated(VerifyInput, request))
        return Response({"detail": "Your company is ready. Sign in to begin your trial."})


class LeadInput(EmailInput):
    request_key = serializers.UUIDField()
    name = serializers.CharField(max_length=120)
    company = serializers.CharField(max_length=160)
    phone = serializers.CharField(max_length=40, allow_blank=True, default="")
    requirements = serializers.CharField(max_length=4000)
    kind = serializers.ChoiceField(choices=["DEMO", "SALES"])
    consent = serializers.BooleanField()
    website = serializers.CharField(max_length=200, allow_blank=True, default="")

    def validate_consent(self, value):
        if not value:
            raise serializers.ValidationError("Please acknowledge the contact notice.")
        return value


class LeadCapture(PublicIdentityView):
    @extend_schema(request=LeadInput, responses={202: OpenApiTypes.OBJECT})
    @transaction.atomic
    def post(self, request):
        values = validated(LeadInput, request)
        values.pop("consent")
        spam = values.pop("website")
        if not spam:
            key = values.pop("request_key")
            lead, created = SalesLead.objects.get_or_create(request_key=key, defaults=values)
            if not created and any(
                getattr(lead, field) != value for field, value in values.items()
            ):
                raise serializers.ValidationError("This request key has already been used.")
        return Response(
            {
                "detail": "Your request has been received. Keep this reference for follow-up.",
                "reference": str(request.data["request_key"]),
            },
            status=202,
        )


class BillingOverview(APIView):
    permission_classes = [TenantAdminPermission]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        sub = (
            Subscription.objects.select_related("plan")
            .filter(organization=request.user.organization)
            .first()
        )
        recurring = (
            ProviderSubscription.objects.filter(code=sub.provider_subscription).first()
            if sub
            else None
        )
        return Response(
            {
                "provider": settings.BILLING_PROVIDER,
                "managed": sub is None or sub.state == "MANAGED",
                "usage": usage(request.user.organization),
                "subscription": {
                    "state": sub.state,
                    "writable": writable(sub),
                    "plan": plan_data(sub.plan),
                    "billing_email": sub.billing_email,
                    "trial_ends_at": sub.trial_ends_at,
                    "period_ends_at": sub.period_ends_at,
                    "grace_ends_at": sub.grace_ends_at,
                    "cancel_at_period_end": sub.cancel_at_period_end,
                    "recurring_status": recurring.status if recurring else None,
                    "provider_setup_pending": sub.provider == "paystack_test"
                    and not sub.provider_subscription,
                }
                if sub
                else None,
                "history": [
                    checkout_data(c)
                    for c in Checkout.objects.filter(
                        organization=request.user.organization
                    ).order_by("-created_at")[:100]
                ],
            }
        )

    @extend_schema(request=EmailInput, responses=OpenApiTypes.OBJECT)
    @transaction.atomic
    def patch(self, request):
        values = validated(EmailInput, request)
        org = Organization.objects.select_for_update().get(pk=request.user.organization_id)
        sub = get_object_or_404(Subscription.objects.select_for_update(), organization=org)
        sub.billing_email = values["email"]
        sub.save(update_fields=["billing_email", "updated_at"])
        audit(org, request.user, "BILLING_CONTACT_UPDATED", sub.pk)
        return Response({"detail": "Billing contact updated."})


class CheckoutInput(StrictSerializer):
    plan_id = serializers.UUIDField()
    request_key = serializers.UUIDField()


class CheckoutView(APIView):
    permission_classes = [TenantAdminPermission]
    throttle_classes = [IdentityThrottle]

    @extend_schema(request=CheckoutInput, responses={201: OpenApiTypes.OBJECT})
    def post(self, request):
        checkout = billing.initialize_checkout(
            actor=request.user, **validated(CheckoutInput, request)
        )
        return Response(checkout_data(checkout), status=201)


class SandboxInput(StrictSerializer):
    outcome = serializers.ChoiceField(choices=["SUCCEEDED", "FAILED", "REFUNDED", "CHARGEBACK"])


class SandboxPayment(APIView):
    permission_classes = [TenantAdminPermission]
    throttle_classes = [IdentityThrottle]

    @extend_schema(request=SandboxInput, responses=OpenApiTypes.OBJECT)
    def post(self, request, pk):
        event = billing.simulate(
            actor=request.user, checkout_id=pk, **validated(SandboxInput, request)
        )
        result = billing.process_event(event.pk)
        return Response({"status": result.status, "sandbox": True})


class CancelSubscription(APIView):
    permission_classes = [TenantAdminPermission]

    @extend_schema(request=None, responses=OpenApiTypes.OBJECT)
    def post(self, request):
        billing.cancel(actor=request.user)
        return Response(
            {
                "detail": "Cancellation recorded. Paid access continues to the period end. "
                "Your records remain available to read and export."
            }
        )


class BillingWebhook(PublicIdentityView):
    throttle_classes = []  # Signature validation and ingress body/rate limits protect this route.

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def post(self, request):
        event = billing.receive_webhook(
            body=request.body,
            signature=request.headers.get(
                "x-paystack-signature", request.headers.get("x-assetflow-signature", "")
            ),
        )
        return Response({"received": True, "event": event.pk}, status=200)


class PlatformOverview(APIView):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        require_operator(request.user)
        search = request.query_params.get("search", "")[:100]
        tenants = (
            Organization.objects.filter(name__icontains=search)
            .select_related("subscription")
            .order_by("name")[:100]
        )
        # Support operators see commercial metadata, never tenant asset/accounting records.
        return Response(
            {
                "tenants": [
                    {
                        "id": str(o.pk),
                        "name": o.name,
                        "code": o.code,
                        "is_active": o.is_active,
                        "subscription": o.subscription.state
                        if hasattr(o, "subscription")
                        else "MANAGED",
                    }
                    for o in tenants
                ],
                "new_leads": SalesLead.objects.filter(status="NEW").count(),
                "failed_webhooks": list(
                    BillingEvent.objects.filter(status="FAILED").values(
                        "id", "reference", "attempts", "last_error"
                    )[:100]
                ),
            }
        )


class TenantStateInput(StrictSerializer):
    is_active = serializers.BooleanField()
    reason = serializers.CharField(max_length=500)


class TenantState(APIView):
    @extend_schema(request=TenantStateInput, responses=OpenApiTypes.OBJECT)
    @transaction.atomic
    def post(self, request, pk):
        require_operator(request.user)
        values = validated(TenantStateInput, request)
        org = get_object_or_404(Organization.objects.select_for_update(), pk=pk)
        org.is_active = values["is_active"]
        org.save(update_fields=["is_active", "updated_at"])
        if not org.is_active:
            IdentityTicket.objects.filter(
                organization=org, consumed_at__isnull=True, revoked_at__isnull=True
            ).update(revoked_at=timezone.now())
        audit(
            org,
            request.user,
            "TENANT_RESUMED" if org.is_active else "TENANT_SUSPENDED",
            org.pk,
            metadata={"reason": values["reason"]},
        )
        PlatformEvent.objects.create(
            actor=request.user, action="TENANT_STATE_CHANGED", target=str(org.pk)
        )
        return Response({"is_active": org.is_active})


class ResendManagedInvitation(APIView):
    throttle_classes = [IdentityThrottle]

    @extend_schema(request=None, responses=OpenApiTypes.OBJECT)
    @transaction.atomic
    def post(self, request, pk):
        from accounts.identity_services import issue_ticket

        require_operator(request.user)
        org = get_object_or_404(Organization.objects.select_for_update(), pk=pk)
        record = get_object_or_404(ManagedProvision.objects.select_for_update(), organization=org)
        if User.objects.filter(organization=org).exists() or record.invitation.revoked_at:
            raise serializers.ValidationError(
                "Activation is unavailable or already completed. Review tenant status."
            )
        record.invitation = issue_ticket(
            purpose="INVITE",
            email=record.parameters["email"],
            organization=org,
            role="ADMIN",
            activates=True,
        )
        record.save(update_fields=["invitation"])
        audit(org, request.user, "ADMIN_ACTIVATION_REISSUED", record.invitation_id)
        return Response({"detail": "A replacement administrator activation email is queued."})


class LeadStatusInput(StrictSerializer):
    id = serializers.UUIDField()
    status = serializers.ChoiceField(choices=SalesLead._meta.get_field("status").choices)


class SalesInbox(APIView):
    @extend_schema(responses={200: {"type": "array", "items": {"type": "object"}}})
    def get(self, request):
        require_operator(request.user)
        return Response(
            list(
                SalesLead.objects.order_by("-created_at").values(
                    "id",
                    "name",
                    "email",
                    "company",
                    "phone",
                    "requirements",
                    "kind",
                    "status",
                    "created_at",
                )[:100]
            )
        )

    @extend_schema(request=LeadStatusInput, responses=OpenApiTypes.OBJECT)
    def patch(self, request):
        require_operator(request.user)
        values = validated(LeadStatusInput, request)
        lead = get_object_or_404(SalesLead, pk=values["id"])
        lead.status = values["status"]
        lead.save(update_fields=["status", "updated_at"])
        PlatformEvent.objects.create(
            actor=request.user, action="LEAD_STATUS_CHANGED", target=str(lead.pk)
        )
        return Response({"status": lead.status})
