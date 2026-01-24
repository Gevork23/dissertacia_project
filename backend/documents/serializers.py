from rest_framework import serializers
from .models import Document, DocumentVersion


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ["id", "title", "description", "created_at", "updated_at"]


class DocumentVersionSerializer(serializers.ModelSerializer):
    chunks_count = serializers.IntegerField(source="chunks.count", read_only=True)

    class Meta:
        model = DocumentVersion
        fields = [
            "id",
            "document",
            "version_number",
            "source_filename",
            "file",
            "extracted_text",
            "chunks_count",
            "created_at",
        ]
        read_only_fields = ["extracted_text", "chunks_count", "created_at"]
