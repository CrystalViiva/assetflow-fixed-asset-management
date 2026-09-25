"""Organization and operating-structure foundation models."""

import uuid

from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Organization(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=160)
    code = models.CharField(max_length=32, unique=True)
    legal_name = models.CharField(max_length=240, blank=True)
    currency = models.CharField(max_length=3, default="NGN")
    timezone = models.CharField(max_length=64, default="Africa/Lagos")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return f"{self.code} — {self.name}"


class Department(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="departments"
    )
    name = models.CharField(max_length=160)
    code = models.CharField(max_length=32)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "code"), name="uniq_department_code_per_org"
            ),
        ]

    def __str__(self):
        return f"{self.code} — {self.name}"


class Location(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="locations"
    )
    name = models.CharField(max_length=160)
    code = models.CharField(max_length=32)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, default="Nigeria")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "code"), name="uniq_location_code_per_org"
            ),
        ]

    def __str__(self):
        return f"{self.code} — {self.name}"
