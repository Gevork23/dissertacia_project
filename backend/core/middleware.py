# backend/core/middleware.py
from __future__ import annotations

import logging
import time

from django.http import HttpRequest, HttpResponse

from .logging import new_request_id, set_request_id

logger = logging.getLogger("core.request")


class RequestLogMiddleware:
    """
    Logs each request start/end with request_id.
    Adds X-Request-ID header to response.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        rid = request.headers.get("X-Request-ID") or new_request_id()
        set_request_id(rid)

        start = time.perf_counter()
        method = request.method
        path = request.get_full_path()
        ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[
            0
        ].strip() or request.META.get("REMOTE_ADDR", "-")

        logger.info("REQ start %s %s ip=%s", method, path, ip)

        try:
            response = self.get_response(request)
        except Exception:
            dur_ms = int((time.perf_counter() - start) * 1000)
            logger.exception("REQ error %s %s dur_ms=%s", method, path, dur_ms)
            raise

        dur_ms = int((time.perf_counter() - start) * 1000)
        status = getattr(response, "status_code", "?")
        logger.info("REQ done %s %s status=%s dur_ms=%s", method, path, status, dur_ms)

        try:
            response["X-Request-ID"] = rid
        except Exception:
            pass

        return response
