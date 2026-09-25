import pytest
from django.db import IntegrityError, transaction

from accounts.models import User, UserRole


@pytest.mark.django_db
def test_create_user_normalizes_email_hashes_password_and_applies_role():
    user = User.objects.create_user(" Finance@Example.COM ", "strong-password")

    assert user.email == "finance@example.com"
    assert user.check_password("strong-password")
    assert user.password != "strong-password"
    assert user.role == UserRole.EMPLOYEE
    assert user.is_active
    assert not user.is_staff


@pytest.mark.django_db
def test_email_is_unique():
    User.objects.create_user("finance@example.com", "strong-password")

    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.create_user("FINANCE@example.com", "another-password")


@pytest.mark.django_db
def test_user_role_can_be_selected():
    user = User.objects.create_user(
        "accountant@example.com", "strong-password", role=UserRole.ACCOUNTANT
    )

    assert user.role == UserRole.ACCOUNTANT


@pytest.mark.django_db
def test_superuser_is_compatible_with_django_admin():
    user = User.objects.create_superuser("admin@example.com", "strong-password")

    assert user.is_staff
    assert user.is_superuser
    assert user.is_active
    assert user.role == UserRole.ADMIN


def test_manager_requires_email():
    with pytest.raises(ValueError, match="email address is required"):
        User.objects.create_user("", "strong-password")
