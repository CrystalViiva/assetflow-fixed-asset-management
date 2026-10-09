from datetime import timedelta
from uuid import uuid4

from django.core.files.base import ContentFile
from django.core.files.storage import storages
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.identity_services import require_operator
from accounts.models import IdentityDelivery
from operations.models import TaskFailure, WorkerPulse


def operational_health():
    pulse = WorkerPulse.objects.filter(pk="default").first()
    worker_ok = bool(pulse and pulse.seen_at >= timezone.now() - timedelta(minutes=3))
    storage_ok = False
    storage = storages["assetflow_private"]
    name = None
    try:
        name = storage.save(f"health/{uuid4().hex}.txt", ContentFile(b"health"))
        with storage.open(name, "rb") as item:
            storage_ok = item.read() == b"health"
    except Exception:
        storage_ok = False
    finally:
        if name:
            try:
                storage.delete(name)
            except Exception:
                storage_ok = False
    return {
        "worker_recent": worker_ok,
        "private_storage": storage_ok,
        "mail_pending": IdentityDelivery.objects.filter(
            sent_at__isnull=True, attempts__lt=8
        ).count(),
        "mail_failed": IdentityDelivery.objects.filter(sent_at__isnull=True, attempts__gte=8)
        .exclude(last_error="ticket_closed")
        .count(),
        "task_failures_24h": TaskFailure.objects.filter(
            occurred_at__gte=timezone.now() - timedelta(days=1)
        ).count(),
    }


class OperationalHealth(APIView):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        require_operator(request.user)
        return Response(operational_health())
