"""Small operational endpoints for the Django service."""

from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def health_check(_request):
    """Report process health without exposing configuration or credentials."""
    return JsonResponse({"status": "ok", "service": "assetflow-api"})
