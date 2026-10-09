"""Database-backed atomic limits shared by web processes; no proxy header trust."""

import hashlib
import ipaddress
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.throttling import BaseThrottle

from accounts.models import RateBucket


class IdentityThrottle(BaseThrottle):
    limit = 20
    seconds = 600

    def allow_request(self, request, view):
        remote = request.META.get("REMOTE_ADDR", "unknown")
        try:
            address = ipaddress.ip_address(remote)
            if any(
                address in ipaddress.ip_network(network)
                for network in settings.TRUSTED_PROXY_NETWORKS
            ):
                remote = str(ipaddress.ip_address(request.META.get("HTTP_X_REAL_IP", remote)))
        except ValueError:
            pass
        identity = str(request.user.pk) if request.user.is_authenticated else remote
        key = hashlib.sha256(f"{view.__class__.__name__}:{identity}".encode()).hexdigest()
        now = timezone.now()
        with transaction.atomic():
            RateBucket.objects.get_or_create(key=key, defaults={"started_at": now})
            bucket = RateBucket.objects.select_for_update().get(pk=key)
            if now >= bucket.started_at + timedelta(seconds=self.seconds):
                bucket.started_at, bucket.count = now, 0
            self.remaining = max(1, self.seconds - (now - bucket.started_at).total_seconds())
            if bucket.count >= self.limit:
                return False
            bucket.count += 1
            bucket.save(update_fields=["started_at", "count"])
        return True

    def wait(self):
        return self.remaining


class RefreshThrottle(IdentityThrottle):
    limit = 120
    seconds = 60
