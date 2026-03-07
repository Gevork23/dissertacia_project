from django.db import models


class Document(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-created_at"]

    def __str__(self) -> str:
        return self.title


class DocumentVersion(models.Model):
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="versions",
    )
    version_number = models.PositiveIntegerField()
    source_filename = models.CharField(max_length=255, blank=True)
    file = models.FileField(upload_to="documents/%Y/%m/%d/")
    extracted_text = models.TextField(blank=True)
    normalized_text = models.TextField(blank=True)
    content_hash = models.CharField(max_length=64, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["document", "version_number"],
                name="uniq_document_version_number",
            )
        ]

    def __str__(self) -> str:
        return f"{self.document.title} v{self.version_number}"


class Chunk(models.Model):
    version = models.ForeignKey(
        DocumentVersion,
        on_delete=models.CASCADE,
        related_name="chunks",
    )
    chunk_index = models.PositiveIntegerField()
    section_path = models.CharField(max_length=512, blank=True)
    heading = models.CharField(max_length=255, blank=True)
    text = models.TextField()
    text_hash = models.CharField(max_length=64, blank=True)
    token_count = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["chunk_index"]
        indexes = [
            models.Index(fields=["version", "chunk_index"]),
            models.Index(fields=["text_hash"]),
        ]

    def __str__(self) -> str:
        return f"Chunk {self.chunk_index} ({self.version})"


class ChunkAnalysis(models.Model):
    chunk = models.ForeignKey(
        Chunk,
        on_delete=models.CASCADE,
        related_name="analyses",
    )
    extraction_method = models.CharField(max_length=32, default="rule_based")
    entities = models.JSONField(default=list)
    entities_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["chunk_id", "-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["chunk", "extraction_method"],
                name="uniq_chunk_analysis_method",
            )
        ]
        indexes = [
            models.Index(fields=["chunk", "extraction_method"]),
        ]

    def __str__(self) -> str:
        return (
            f"ChunkAnalysis chunk={self.chunk_id} "
            f"method={self.extraction_method} "
            f"entities={self.entities_count}"
        )


class GeneratedQuiz(models.Model):
    from_version = models.ForeignKey(
        "DocumentVersion",
        on_delete=models.CASCADE,
        related_name="generated_quizzes_from",
    )
    to_version = models.ForeignKey(
        "DocumentVersion",
        on_delete=models.CASCADE,
        related_name="generated_quizzes_to",
    )
    title = models.CharField(max_length=255, blank=True)
    payload = models.JSONField(default=dict)
    questions_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return (
            f"Quiz {self.id}: "
            f"{self.from_version_id} -> {self.to_version_id} "
            f"({self.questions_count} questions)"
        )


class QuizAttempt(models.Model):
    quiz = models.ForeignKey(
        "GeneratedQuiz",
        on_delete=models.CASCADE,
        related_name="attempts",
    )
    participant_name = models.CharField(max_length=255, blank=True)
    answers = models.JSONField(default=list)
    score = models.PositiveIntegerField(default=0)
    total_questions = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return (
            f"Attempt {self.id} for quiz {self.quiz_id}: "
            f"{self.score}/{self.total_questions}"
        )