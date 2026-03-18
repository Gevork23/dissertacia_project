from __future__ import annotations

import logging

from django.db.models import Count, Max
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from .models import Document, DocumentVersion
from .serializers import (
    DocumentSerializer,
    DocumentVersionCreateSerializer,
    DocumentVersionSerializer,
)

logger = logging.getLogger("documents.api")


class DocumentViewSet(viewsets.ModelViewSet):
    serializer_class = DocumentSerializer

    def get_queryset(self):
        return Document.objects.annotate(
            versions_count=Count("versions"),
            latest_version_number=Max("versions__version_number"),
        ).all()

    @action(
        detail=True,
        methods=["get", "post"],
        parser_classes=[MultiPartParser, FormParser],
    )
    def versions(self, request, pk=None):
        document = self.get_object()

        if request.method == "GET":
            queryset = document.versions.select_related("document").all()
            serializer = DocumentVersionSerializer(
                queryset,
                many=True,
                context={"request": request},
            )
            return Response(serializer.data, status=status.HTTP_200_OK)

        serializer = DocumentVersionCreateSerializer(
            data=request.data,
            context={"request": request, "document": document},
        )
        serializer.is_valid(raise_exception=True)
        version = serializer.save()

        logger.info(
            "Document version uploaded: document_id=%s version_id=%s version_number=%s",
            document.id,
            version.id,
            version.version_number,
        )

        response_serializer = DocumentVersionSerializer(
            version,
            context={"request": request},
        )
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class DocumentVersionViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        queryset = DocumentVersion.objects.select_related("document").all()
        document_id = self.request.query_params.get("document")
        if document_id:
            queryset = queryset.filter(document_id=document_id)
        return queryset

    def get_serializer_class(self):
        if self.action == "create":
            return DocumentVersionCreateSerializer
        return DocumentVersionSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        version = serializer.save()

        logger.info(
            "Document version uploaded: document_id=%s version_id=%s version_number=%s",
            version.document_id,
            version.id,
            version.version_number,
        )

        response_serializer = DocumentVersionSerializer(
            version,
            context={"request": request},
        )
        headers = self.get_success_headers(response_serializer.data)
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
            headers=headers,
        )

    @action(detail=True, methods=["get"])
    def text(self, request, pk=None):
        version = self.get_object()
        logger.info("Get extracted text: version_id=%s", version.id)
        return Response(
            {
                "id": version.id,
                "extracted_text": version.extracted_text,
                "normalized_text": version.normalized_text,
                "content_hash": version.content_hash,
            }
        )
