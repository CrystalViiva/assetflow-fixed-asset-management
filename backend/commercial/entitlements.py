"""Server authority for subscription access. Expiry is evaluated on every request."""

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from commercial.models import Subscription
from organizations.models import Organization


def writable(subscription):
    now = timezone.now()
    if subscription.state == "MANAGED":
        return True
    if subscription.state in {"SUSPENDED", "CANCELED"}:
        return False
    if subscription.state == "TRIAL":
        return bool(subscription.trial_ends_at and subscription.trial_ends_at > now)
    if subscription.state == "ACTIVE":
        return bool(subscription.period_ends_at and subscription.period_ends_at > now)
    return bool(subscription.grace_ends_at and subscription.grace_ends_at > now)


def enforce_request(user, request):
    if not user.organization_id or request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    # Account recovery, billing and supported exports remain available in read-only mode.
    if request.path.startswith(("/api/v1/auth/", "/api/v1/billing/")):
        return
    if request.path.startswith(
        ("/api/v1/reports/", "/api/v1/report-snapshots/", "/api/v1/report-exports/")
    ):
        return
    subscription = Subscription.objects.filter(organization_id=user.organization_id).first()
    if subscription and not writable(subscription):
        raise PermissionDenied(
            "Your subscription permits read-only access. "
            "Contact your administrator or update billing."
        )


def usage(organization):
    from accounts.models import User
    from assets.models import Asset

    return {
        "active_users": User.objects.filter(organization=organization, is_active=True).count(),
        "registered_assets": Asset.objects.filter(organization=organization).count(),
    }


def require_capacity(organization, dimension):
    """Caller holds this organization lock through the consequential insert."""
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("Entitlement checks require the surrounding write transaction.")
    Organization.objects.select_for_update().get(pk=organization.pk)
    subscription = (
        Subscription.objects.select_related("plan").filter(organization=organization).first()
    )
    if subscription is None:  # Existing/managed organizations retain their agreed access.
        return
    if not writable(subscription):
        raise PermissionDenied("This subscription is read-only.")
    limit = getattr(subscription.plan, dimension)
    if limit is not None and usage(organization)[dimension] >= limit:
        raise PermissionDenied(
            f"The plan limit for {dimension.replace('_', ' ')} has been reached."
        )
