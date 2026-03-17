from __future__ import annotations

import logging
from typing import Any

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger("core.api")


def _normalize_error_payload(data: Any) -> dict[str, Any]:
    if isinstance(data, dict):
        return data
    if isinstance(data, list):
        return {"errors": data}
    return {"detail": str(data)}


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    request = context.get("request")

    if response is not None:
        payload = {
            "status": "error",
            "code": response.status_code,
            **_normalize_error_payload(response.data),
        }
        if request is not None:
            payload["path"] = request.get_full_path()
        response.data = payload
        return response

    logger.exception("Unhandled API exception", exc_info=exc)
    payload = {
        "status": "error",
        "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
        "detail": "Internal server error.",
    }
    if request is not None:
        payload["path"] = request.get_full_path()
    return Response(payload, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
