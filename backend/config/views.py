"""Small operational endpoints for the Django service."""

import logging

from django.db import connections
from django.http import JsonResponse
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)


@require_GET
def health_check(_request):
    """Report process liveness without exposing configuration or credentials."""
    return JsonResponse({"status": "ok", "service": "assetflow-api"})


@require_GET
def readiness_check(_request):
    """Check the transactional database before a deployment routes customer traffic."""
    try:
        connections["default"].ensure_connection()
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        logger.exception("Readiness check failed for the default database")
        return JsonResponse({"status": "not_ready", "service": "assetflow-api"}, status=503)
    return JsonResponse({"status": "ready", "service": "assetflow-api"})
