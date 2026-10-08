"""Per-request correlation IDs for API logs and reverse-proxy support cases."""

import contextvars
import uuid

request_id = contextvars.ContextVar("assetflow_request_id", default="-")


class RequestIdFilter:
    def filter(self, record):
        record.request_id = request_id.get()
        return True


class RequestIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = request_id.set(uuid.uuid4().hex)
        request.assetflow_request_id = request_id.get()
        try:
            response = self.get_response(request)
            response["X-Request-ID"] = request_id.get()
            return response
        finally:
            request_id.reset(token)
