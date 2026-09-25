"""Consistent public error format for DRF API failures."""

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import (
    AuthenticationFailed,
    NotAuthenticated,
    NotFound,
    PermissionDenied,
    ValidationError,
)
from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    if isinstance(exc, DjangoValidationError):
        details = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
        exc = ValidationError(details)

    response = exception_handler(exc, context)
    if response is None:
        return None

    if isinstance(exc, ValidationError):
        code = "VALIDATION_ERROR"
        message = "The request contains invalid fields."
        details = response.data
    elif isinstance(exc, (AuthenticationFailed, NotAuthenticated)):
        code = "AUTHENTICATION_ERROR"
        message = "Valid authentication credentials are required."
        details = {}
    elif isinstance(exc, PermissionDenied):
        code = "PERMISSION_DENIED"
        message = "You do not have permission to perform this action."
        details = {}
    elif isinstance(exc, NotFound):
        code = "NOT_FOUND"
        message = "The requested resource was not found."
        details = {}
    else:
        code = "API_ERROR"
        message = "The request could not be completed."
        details = {}

    response.data = {
        "success": False,
        "error": {"code": code, "message": message, "details": details},
    }
    return response
