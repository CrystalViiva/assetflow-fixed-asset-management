import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class SalesLead(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request_key = models.UUIDField(unique=True)
    name = models.CharField(max_length=120)
    email = models.EmailField()
    company = models.CharField(max_length=160)
    phone = models.CharField(max_length=40, blank=True)
    requirements = models.TextField(max_length=4000)
    kind = models.CharField(max_length=12, choices=[("DEMO", "Demo"), ("SALES", "Sales")])
    notice_version = models.CharField(max_length=32, default="contact-v1")
    status = models.CharField(
        max_length=16,
        default="NEW",
        choices=[(s, s) for s in ("NEW", "CONTACTED", "QUALIFIED", "CLOSED")],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Registration(models.Model):
    email = models.EmailField(unique=True)
    company_name = models.CharField(max_length=160)
    currency = models.CharField(max_length=3)
    timezone = models.CharField(max_length=64)
    ticket = models.OneToOneField("accounts.IdentityTicket", on_delete=models.PROTECT)
    organization = models.OneToOneField(
        "organizations.Organization", on_delete=models.PROTECT, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)


class Plan(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.SlugField(max_length=40)
    version = models.PositiveIntegerField(default=1)
    name = models.CharField(max_length=80)
    currency = models.CharField(max_length=3, default="NGN")
    monthly_amount = models.DecimalField(max_digits=12, decimal_places=2)
    active_users = models.PositiveIntegerField(null=True)
    registered_assets = models.PositiveIntegerField(null=True)
    trial_days = models.PositiveIntegerField(default=14)
    is_public = models.BooleanField(default=True)
    is_sandbox = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            original = type(self).objects.get(pk=self.pk)
            if any(
                getattr(original, field.attname) != getattr(self, field.attname)
                for field in self._meta.concrete_fields
                if field.name != "is_public"
            ):
                raise ValidationError(
                    "Publish a new plan version instead of changing existing terms."
                )
        super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["code", "version"], name="unique_plan_version")
        ]


class Subscription(models.Model):
    organization = models.OneToOneField(
        "organizations.Organization", primary_key=True, on_delete=models.PROTECT
    )
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True)
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    state = models.CharField(
        max_length=16,
        default="TRIAL",
        choices=[
            (s, s) for s in ("MANAGED", "TRIAL", "ACTIVE", "PAST_DUE", "CANCELED", "SUSPENDED")
        ],
    )
    trial_ends_at = models.DateTimeField(null=True)
    period_ends_at = models.DateTimeField(null=True)
    grace_ends_at = models.DateTimeField(null=True)
    cancel_at_period_end = models.BooleanField(default=False)
    canceled_at = models.DateTimeField(null=True)
    billing_email = models.EmailField()
    provider = models.CharField(max_length=24, default="local_sandbox")
    provider_customer = models.CharField(max_length=120, blank=True)
    provider_subscription = models.CharField(max_length=120, blank=True)
    last_event_at = models.DateTimeField(null=True)
    entitlement_checkout = models.ForeignKey(
        "Checkout", on_delete=models.PROTECT, null=True, related_name="entitled_subscriptions"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Checkout(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT)
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    request_key = models.UUIDField()
    amount_minor = models.PositiveBigIntegerField()
    currency = models.CharField(max_length=3)
    status = models.CharField(max_length=16, default="PENDING")
    provider = models.CharField(max_length=24)
    provider_reference = models.CharField(max_length=120, unique=True)
    provider_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    settled_at = models.DateTimeField(null=True)
    # Authoritative deterministic fake-provider ledger; never exposed for tenant writes.
    sandbox_status = models.CharField(max_length=16, default="PENDING")
    sandbox_sequence = models.PositiveIntegerField(default=0)
    sandbox_updated_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "request_key"], name="checkout_idempotency_per_org"
            )
        ]


class BillingEvent(models.Model):
    id = models.CharField(max_length=64, primary_key=True)
    provider = models.CharField(max_length=24)
    reference = models.CharField(max_length=120)
    event_type = models.CharField(max_length=80)
    status = models.CharField(max_length=16, default="PENDING")
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.CharField(max_length=100, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True)
