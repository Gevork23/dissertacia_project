from rest_framework import serializers

from .models import Document, DocumentVersion, GeneratedQuiz, QuizAttempt


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
            "created_at",
        ]
        read_only_fields = [
            "id",
            "payload",
            "questions_count",
            "created_at",
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
            "created_at",
        ]
        read_only_fields = [
            "id",
            "score",
            "total_questions",
            "created_at",
        ]