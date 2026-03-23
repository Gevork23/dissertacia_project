from __future__ import annotations

from pathlib import Path

from rest_framework import serializers

from ..domain.text_extractors import EmptyExtractedTextError, TextExtractionError
from ..models import Document, DocumentVersion, GeneratedQuiz, QuizAttempt
from ..services.versioning import (
    DuplicateDocumentVersionError,
    InvalidDocumentVersionFileError,
    create_uploaded_document_version,
)


class DocumentSerializer(serializers.ModelSerializer):
    versions_count = serializers.SerializerMethodField()
    latest_version_number = serializers.SerializerMethodField()
    current_version_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Document
        fields = [
            "id",
            "document_key",
            "title",
            "description",
            "current_version_id",
            "versions_count",
            "latest_version_number",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "document_key",
            "current_version_id",
            "versions_count",
            "latest_version_number",
            "created_at",
            "updated_at",
        ]

    def validate_title(self, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError("Document title cannot be empty.")
        return cleaned

    def get_versions_count(self, obj):
        annotated_value = getattr(obj, "versions_count", None)
        if annotated_value is not None:
            return annotated_value
        return obj.versions.count()

    def get_latest_version_number(self, obj):
        if obj.current_version_id:
            return obj.current_version.version_number
        annotated_value = getattr(obj, "latest_version_number", None)
        if annotated_value is not None:
            return annotated_value
        latest_version = obj.versions.order_by("-version_number").first()
        return latest_version.version_number if latest_version else None


class DocumentVersionSerializer(serializers.ModelSerializer):
    chunks_count = serializers.SerializerMethodField()

    class Meta:
        model = DocumentVersion
        fields = [
            "id",
            "document",
            "version_number",
            "source_filename",
            "source_revision_id",
            "effective_date",
            "file",
            "file_size",
            "content_type",
            "extracted_text",
            "chunks_count",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "version_number",
            "source_filename",
            "source_revision_id",
            "effective_date",
            "file_size",
            "content_type",
            "extracted_text",
            "chunks_count",
            "created_at",
        ]

    def get_chunks_count(self, obj):
        annotated_value = getattr(obj, "chunks_count", None)
        if annotated_value is not None:
            return annotated_value
        return obj.chunks.count()


class DocumentVersionCreateSerializer(serializers.ModelSerializer):
    document = serializers.PrimaryKeyRelatedField(
        queryset=Document.objects.all(),
        required=False,
    )
    source_filename = serializers.CharField(required=False, allow_blank=True)
    source_revision_id = serializers.CharField(required=False, allow_blank=True)
    effective_date = serializers.DateField(required=False, allow_null=True)

    class Meta:
        model = DocumentVersion
        fields = [
            "id",
            "document",
            "source_filename",
            "source_revision_id",
            "effective_date",
            "file",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        document = attrs.get("document") or self.context.get("document")
        if document is None:
            raise serializers.ValidationError({"document": "This field is required."})
        attrs["document"] = document
        return attrs

    def validate_source_filename(self, value: str) -> str:
        return Path(value.strip()).name

    def create(self, validated_data):
        try:
            return create_uploaded_document_version(
                document=validated_data["document"],
                uploaded_file=validated_data["file"],
                source_filename=validated_data.get("source_filename", ""),
                source_revision_id=validated_data.get("source_revision_id", ""),
                effective_date=validated_data.get("effective_date"),
            )
        except InvalidDocumentVersionFileError as error:
            raise serializers.ValidationError({"file": [str(error)]}) from error
        except DuplicateDocumentVersionError as error:
            raise serializers.ValidationError({"file": [str(error)]}) from error
        except EmptyExtractedTextError as error:
            raise serializers.ValidationError({"file": [str(error)]}) from error
        except TextExtractionError as error:
            raise serializers.ValidationError({"file": [str(error)]}) from error


class ChangeClassificationSerializer(serializers.Serializer):
    primary_type = serializers.CharField()
    matched_types = serializers.ListField(child=serializers.CharField())
    scores = serializers.DictField(child=serializers.FloatField())
    rationale = serializers.ListField(child=serializers.CharField())


class ChunkDiffSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    chunk_index = serializers.IntegerField()
    heading = serializers.CharField(allow_blank=True)
    section_path = serializers.CharField(allow_blank=True)
    text = serializers.CharField()
    text_hash = serializers.CharField(allow_blank=True)
    change_classification = ChangeClassificationSerializer(required=False)


class ModifiedChunkDiffSerializer(serializers.Serializer):
    from_chunk = ChunkDiffSerializer()
    to_chunk = ChunkDiffSerializer()
    similarity = serializers.FloatField()
    match_reason = serializers.CharField()
    change_classification = ChangeClassificationSerializer(required=False)


class MovedChunkDiffSerializer(serializers.Serializer):
    from_chunk = ChunkDiffSerializer()
    to_chunk = ChunkDiffSerializer()
    change_classification = ChangeClassificationSerializer(required=False)


class VersionShortSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    document_id = serializers.IntegerField()
    version_number = serializers.IntegerField()
    created_at = serializers.DateTimeField()


class VersionDiffSummarySerializer(serializers.Serializer):
    added = serializers.IntegerField()
    removed = serializers.IntegerField()
    modified = serializers.IntegerField()
    moved = serializers.IntegerField()
    unchanged = serializers.IntegerField()
    by_type = serializers.DictField(child=serializers.IntegerField(), required=False)


class VersionDiffSerializer(serializers.Serializer):
    from_version = VersionShortSerializer()
    to_version = VersionShortSerializer()
    identical = serializers.BooleanField()
    summary = VersionDiffSummarySerializer()
    added = ChunkDiffSerializer(many=True)
    removed = ChunkDiffSerializer(many=True)
    modified = ModifiedChunkDiffSerializer(many=True)
    moved = MovedChunkDiffSerializer(many=True)
    text_diff = serializers.CharField()


class GeneratedQuizSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeneratedQuiz
        fields = [
            "id",
            "from_version",
            "to_version",
            "title",
            "payload",
            "questions_count",
            "status",
            "approved_by_name",
            "approved_at",
            "approval_comment",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "payload",
            "questions_count",
            "approved_at",
            "created_at",
            "updated_at",
        ]


class QuizAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuizAttempt
        fields = [
            "id",
            "quiz",
            "employee",
            "participant_name",
            "answers",
            "score",
            "total_questions",
            "status",
            "created_at",
            "completed_at",
        ]
        read_only_fields = [
            "id",
            "answers",
            "score",
            "total_questions",
            "created_at",
            "completed_at",
        ]
