# backend/documents/views.py
from rest_framework import viewsets, mixins
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Document, DocumentVersion, Chunk
from .serializers import DocumentSerializer, DocumentVersionSerializer
from .text_extractors import extract_text_by_extension
from .text_processing import normalize_text, sha256_hex, chunk_by_paragraphs, chunk_by_structure_ru
from .qdrant_service import index_chunks


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

        # 1) Extract text
        file_path = instance.file.path
        extracted = extract_text_by_extension(file_path)

        if not extracted:
            return

        # 2) Normalize + hashes
        normalized = normalize_text(extracted)
        instance.extracted_text = extracted
        instance.normalized_text = normalized
        instance.content_hash = sha256_hex(normalized)
        instance.save(update_fields=["extracted_text", "normalized_text", "content_hash"])

        # 3) Create chunks
        chunk_items = chunk_by_structure_ru(normalized)

        Chunk.objects.filter(version=instance).delete()  # на всякий случай, если перезалили
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
        
        # 4) Index to Qdrant (vector DB)
        index_chunks(instance.id)

    @action(detail=True, methods=["get"])
    def text(self, request, pk=None):
        version = self.get_object()
        return Response({"id": version.id, "text": version.extracted_text})


