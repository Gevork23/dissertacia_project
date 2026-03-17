from __future__ import annotations

import os
from typing import Any

from django.db import connection
from qdrant_client import QdrantClient
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response


def _check_database() -> dict[str, Any]:
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        row = cursor.fetchone()

    return {
        "status": "ok",
        "engine": connection.vendor,
        "result": row[0] if row else None,
    }


def _check_qdrant() -> dict[str, Any]:
    host = os.environ.get("QDRANT_HOST", "qdrant")
    port = int(os.environ.get("QDRANT_PORT", "6333"))
    timeout = float(os.environ.get("QDRANT_TIMEOUT_SECONDS", "3"))

    client = QdrantClient(host=host, port=port, timeout=timeout)
    collections = client.get_collections()

    return {
        "status": "ok",
        "host": host,
        "port": port,
        "collections_count": len(collections.collections),
    }


@api_view(["GET"])
def health(request):
    checks: dict[str, Any] = {}
    http_status = status.HTTP_200_OK

    try:
        checks["database"] = _check_database()
    except Exception as exc:
        http_status = status.HTTP_503_SERVICE_UNAVAILABLE
        checks["database"] = {
            "status": "error",
            "error": str(exc),
        }

    try:
        checks["qdrant"] = _check_qdrant()
    except Exception as exc:
        http_status = status.HTTP_503_SERVICE_UNAVAILABLE
        checks["qdrant"] = {
            "status": "error",
            "error": str(exc),
        }

    payload = {
        "status": "ok" if http_status == status.HTTP_200_OK else "error",
        "service": "backend",
        "checks": checks,
    }
    return Response(payload, status=http_status)
