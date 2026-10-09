"""Durable one-use identity operations. No plaintext link secrets are stored."""

import uuid

from django.conf import settings
from django.db import models


class IdentityTicket(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    purpose = models.CharField(
        max_length=12, choices=[(x, x) for x in ("INVITE", "RESET", "VERIFY")]
    )
    email = models.EmailField()
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, null=True
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True)
    role = models.CharField(max_length=32, default="EMPLOYEE")
    department = models.ForeignKey("organizations.Department", on_delete=models.PROTECT, null=True)
    activates_organization = models.BooleanField(default=False)
    password_fingerprint = models.CharField(max_length=128, blank=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True)
    revoked_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["email", "purpose", "created_at"])]


class IdentityDelivery(models.Model):
    ticket = models.OneToOneField(IdentityTicket, on_delete=models.CASCADE)
    attempts = models.PositiveIntegerField(default=0)
    sent_at = models.DateTimeField(null=True)
    next_attempt_at = models.DateTimeField()
    last_error = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ManagedProvision(models.Model):
    key = models.UUIDField(primary_key=True)
    organization = models.OneToOneField("organizations.Organization", on_delete=models.PROTECT)
    invitation = models.OneToOneField(IdentityTicket, on_delete=models.PROTECT)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    parameters = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)


class RateBucket(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    started_at = models.DateTimeField()
    count = models.PositiveIntegerField(default=0)


class PlatformEvent(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True)
    action = models.CharField(max_length=64)
    target = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
