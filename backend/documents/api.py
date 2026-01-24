from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .qdrant_service import search_chunks


@api_view(["GET"])
def search(request):
    q = (request.query_params.get("q") or "").strip()
    if not q:
        return Response(
            {"detail": "Query parameter 'q' is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    limit = int(request.query_params.get("limit", 5))
    document_id = request.query_params.get("document_id")
    version_id = request.query_params.get("version_id")

    results = search_chunks(
        query=q,
        limit=min(max(limit, 1), 20),
        document_id=int(document_id) if document_id else None,
        version_id=int(version_id) if version_id else None,
    )

    return Response({"query": q, "count": len(results), "results": results})
