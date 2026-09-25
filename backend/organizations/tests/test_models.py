import pytest
from django.db import IntegrityError, transaction

from organizations.models import Department, Location, Organization


@pytest.mark.django_db
def test_organization_defaults_and_timestamps():
    organization = Organization.objects.create(name="Acme Nigeria", code="ACME")

    assert organization.currency == "NGN"
    assert organization.timezone == "Africa/Lagos"
    assert organization.is_active
    assert organization.created_at is not None


@pytest.mark.django_db
def test_organization_code_is_unique():
    Organization.objects.create(name="First", code="ACME")

    with pytest.raises(IntegrityError), transaction.atomic():
        Organization.objects.create(name="Second", code="ACME")


@pytest.mark.django_db
def test_department_code_is_unique_per_organization():
    first_org = Organization.objects.create(name="First", code="FIRST")
    second_org = Organization.objects.create(name="Second", code="SECOND")
    Department.objects.create(organization=first_org, name="Finance", code="FIN")
    Department.objects.create(organization=second_org, name="Finance", code="FIN")

    with pytest.raises(IntegrityError), transaction.atomic():
        Department.objects.create(organization=first_org, name="Finance Copy", code="FIN")


@pytest.mark.django_db
def test_location_code_is_unique_per_organization():
    organization = Organization.objects.create(name="Acme Nigeria", code="ACME")
    Location.objects.create(organization=organization, name="Lagos HQ", code="LOS")

    with pytest.raises(IntegrityError), transaction.atomic():
        Location.objects.create(organization=organization, name="Second Lagos", code="LOS")


@pytest.mark.django_db
def test_department_and_location_codes_can_repeat_in_other_organizations():
    organizations = [
        Organization.objects.create(name="First", code="FIRST"),
        Organization.objects.create(name="Second", code="SECOND"),
    ]

    for organization in organizations:
        Department.objects.create(organization=organization, name="Finance", code="FIN")
        Location.objects.create(organization=organization, name="Lagos", code="LOS")
