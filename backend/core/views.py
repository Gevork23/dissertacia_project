from __future__ import annotations

from typing import Any

from django.conf import settings
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
    client = QdrantClient(
        host=settings.QDRANT_HOST,
        port=settings.QDRANT_PORT,
        timeout=settings.QDRANT_TIMEOUT_SECONDS,
    )
    collections = client.get_collections()

    return {
        "status": "ok",
        "host": settings.QDRANT_HOST,
        "port": settings.QDRANT_PORT,
        "collections_count": len(collections.collections),
    }


@api_view(["GET"])
def api_root(request):
    return Response(
        {
            "service": "backend",
            "status": "ok",
            "api": {
                "health": "/api/health/",
                "documents": "/api/documents/",
                "versions": "/api/versions/",
                "compare": "/api/compare/?from_version=<id>&to_version=<id>",
                "documents_v1": "/api/v1/documents/",
                "versions_v1": "/api/v1/versions/",
            },
        },
        status=status.HTTP_200_OK,
    )


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

    if settings.QDRANT_ENABLED:
        try:
            checks["qdrant"] = _check_qdrant()
        except Exception as exc:
            http_status = status.HTTP_503_SERVICE_UNAVAILABLE
            checks["qdrant"] = {
                "status": "error",
                "error": str(exc),
            }
    else:
        checks["qdrant"] = {"status": "disabled"}

    payload = {
        "status": "ok" if http_status == status.HTTP_200_OK else "error",
        "service": "backend",
        "checks": checks,
    }
    return Response(payload, status=http_status)


@api_view(["GET"])
def live(request):
    return Response(
        {"status": "ok", "service": "backend"},
        status=status.HTTP_200_OK,
    )
