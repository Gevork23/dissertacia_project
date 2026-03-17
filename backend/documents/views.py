from __future__ import annotations

import logging
import time

from django.conf import settings
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from .models import Chunk, Document, DocumentVersion
from .qdrant_service import index_chunks
from .serializers import DocumentSerializer, DocumentVersionSerializer
from .text_extractors import extract_text_by_extension
from .text_processing import chunk_by_structure_ru, normalize_text, sha256_hex

logger = logging.getLogger("documents.ingest")


class DocumentViewSet(viewsets.ModelViewSet):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer


class DocumentVersionViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = DocumentVersion.objects.select_related("document").all()
    serializer_class = DocumentVersionSerializer
    parser_classes = [MultiPartParser, FormParser]

    def perform_create(self, serializer):
        instance = serializer.save()
        t0 = time.perf_counter()

        file_path = instance.file.path
        logger.info(
            "Version create: version_id=%s document_id=%s version_number=%s file=%s",
            instance.id,
            instance.document_id,
            instance.version_number,
            file_path,
        )

        t1 = time.perf_counter()
        try:
            extracted = extract_text_by_extension(file_path)
        except Exception:
            logger.exception(
                "Extract failed: version_id=%s file=%s", instance.id, file_path
            )
            raise

        extract_ms = int((time.perf_counter() - t1) * 1000)
        if not extracted:
            logger.warning(
                "Extract returned empty: version_id=%s file=%s extract_ms=%s",
                instance.id,
                file_path,
                extract_ms,
            )
            return

        logger.info(
            "Extract ok: version_id=%s chars=%s extract_ms=%s",
            instance.id,
            len(extracted),
            extract_ms,
        )

        t2 = time.perf_counter()
        normalized = normalize_text(extracted)
        instance.extracted_text = extracted
        instance.normalized_text = normalized
        instance.content_hash = sha256_hex(normalized)
        instance.save(
            update_fields=["extracted_text", "normalized_text", "content_hash"]
        )
        norm_ms = int((time.perf_counter() - t2) * 1000)

        logger.info(
            "Normalize ok: version_id=%s norm_chars=%s norm_ms=%s content_hash=%s",
            instance.id,
            len(normalized),
            norm_ms,
            instance.content_hash,
        )

        t3 = time.perf_counter()
        chunk_items = chunk_by_structure_ru(normalized)
        chunk_ms = int((time.perf_counter() - t3) * 1000)
        logger.info(
            "Chunking ok: version_id=%s chunks=%s chunk_ms=%s",
            instance.id,
            len(chunk_items),
            chunk_ms,
        )

        t4 = time.perf_counter()
        deleted, _ = Chunk.objects.filter(version=instance).delete()
        Chunk.objects.bulk_create(
            [
                Chunk(
                    version=instance,
                    chunk_index=c.chunk_index,
                    heading=c.heading,
                    section_path=c.section_path,
                    text=c.text,
                    text_hash=c.text_hash,
                )
                for c in chunk_items
            ]
        )
        db_ms = int((time.perf_counter() - t4) * 1000)
        logger.info(
            "DB chunks saved: version_id=%s deleted=%s created=%s db_ms=%s",
            instance.id,
            deleted,
            len(chunk_items),
            db_ms,
        )

        if settings.QDRANT_ENABLED:
            t5 = time.perf_counter()
            try:
                points = index_chunks(instance.id)
            except Exception:
                logger.exception("Qdrant indexing failed: version_id=%s", instance.id)
                raise
            qdrant_ms = int((time.perf_counter() - t5) * 1000)
        else:
            points = 0
            qdrant_ms = 0
            logger.info(
                "Qdrant indexing skipped: version_id=%s reason=qdrant_disabled",
                instance.id,
            )

        total_ms = int((time.perf_counter() - t0) * 1000)
        logger.info(
            "Ingest done: version_id=%s points=%s qdrant_ms=%s total_ms=%s",
            instance.id,
            points,
            qdrant_ms,
            total_ms,
        )

    @action(detail=True, methods=["get"])
    def text(self, request, pk=None):
        version = self.get_object()
        logger.info("Get extracted text: version_id=%s", version.id)
        return Response({"id": version.id, "text": version.extracted_text})
