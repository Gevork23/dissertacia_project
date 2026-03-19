from __future__ import annotations

import mimetypes
from pathlib import Path

from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from rest_framework import serializers

from ..domain.text_extractors import (
    EmptyExtractedTextError,
    TextExtractionError,
    process_uploaded_file,
)
from ..models import (
    ALLOWED_DOCUMENT_EXTENSIONS,
    Document,
    DocumentVersion,
    GeneratedQuiz,
    QuizAttempt,
)
from ..services.ingestion import rebuild_version_chunks


class DocumentSerializer(serializers.ModelSerializer):
    versions_count = serializers.SerializerMethodField()
    latest_version_number = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            "id",
            "title",
            "description",
            "versions_count",
            "latest_version_number",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
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
        annotated_value = getattr(obj, "latest_version_number", None)
        if annotated_value is not None:
            return annotated_value
        latest_version = obj.versions.order_by("-version_number").first()
        return latest_version.version_number if latest_version else None


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
            "file_size",
            "content_type",
            "extracted_text",
            "chunks_count",
            "created_at",
        ]


class DocumentVersionCreateSerializer(serializers.ModelSerializer):
    document = serializers.PrimaryKeyRelatedField(
        queryset=Document.objects.all(),
        required=False,
    )
    source_filename = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = DocumentVersion
        fields = ["id", "document", "source_filename", "file"]
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

    def validate_file(self, uploaded_file):
        extension = Path(uploaded_file.name).suffix.lower()
        if extension not in ALLOWED_DOCUMENT_EXTENSIONS:
            allowed = ", ".join(sorted(ALLOWED_DOCUMENT_EXTENSIONS))
            raise serializers.ValidationError(
                f"Unsupported file type. Allowed extensions: {allowed}."
            )

        if getattr(uploaded_file, "size", 0) <= 0:
            raise serializers.ValidationError("Uploaded file is empty.")

        return uploaded_file

    def create(self, validated_data):
        document = validated_data["document"]
        uploaded_file = validated_data["file"]
        source_filename = validated_data.get("source_filename") or uploaded_file.name
        source_filename = Path(source_filename).name
        content_type = (
            getattr(uploaded_file, "content_type", "")
            or mimetypes.guess_type(source_filename)[0]
            or ""
        )
        file_size = getattr(uploaded_file, "size", 0) or 0

        try:
            processed_text = process_uploaded_file(
                uploaded_file=uploaded_file,
                source_filename=source_filename,
            )
        except EmptyExtractedTextError as error:
            raise serializers.ValidationError({"file": [str(error)]}) from error
        except TextExtractionError as error:
            raise serializers.ValidationError({"file": [str(error)]}) from error

        with transaction.atomic():
            locked_document = Document.objects.select_for_update().get(pk=document.pk)
            current_max = (
                locked_document.versions.aggregate(max_number=Max("version_number"))[
                    "max_number"
                ]
                or 0
            )
            version = DocumentVersion.objects.create(
                document=locked_document,
                version_number=current_max + 1,
                source_filename=source_filename,
                file=uploaded_file,
                file_size=file_size,
                content_type=content_type,
                extracted_text=processed_text.extracted_text,
                normalized_text=processed_text.normalized_text,
                content_hash=processed_text.content_hash,
            )
            rebuild_version_chunks(version)
            Document.objects.filter(pk=locked_document.pk).update(
                updated_at=timezone.now()
            )

        return version


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
            "status",
            "approved_by_name",
            "approved_at",
            "approval_comment",
            "created_at",
            "updated_at",
        ]


class QuizAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuizAttempt
        fields = [
            "id",
            "quiz",
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
            "score",
            "total_questions",
            "status",
            "created_at",
            "completed_at",
        ]
