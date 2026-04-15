from pathlib import Path

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone
from django.utils.text import slugify

ALLOWED_DOCUMENT_EXTENSIONS = {".txt", ".pdf", ".docx"}


class DomainValidatedModel(models.Model):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.full_clean(validate_unique=False, validate_constraints=False)
        return super().save(*args, **kwargs)


def document_version_upload_to(instance: "DocumentVersion", filename: str) -> str:
    safe_name = Path(filename).name
    document_id = instance.document_id or "unknown"
    version_number = instance.version_number or "unassigned"
    return f"documents/document_{document_id}/version_{version_number}/{safe_name}"


class Document(models.Model):
    document_key = models.SlugField(
        max_length=160,
        unique=True,
        null=True,
        blank=True,
        editable=False,
        allow_unicode=True,
        verbose_name="Ключ документа",
        help_text="Устойчивый идентификатор документа внутри системы.",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    current_version = models.ForeignKey(
        "DocumentVersion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-created_at"]

    def __str__(self) -> str:
        return self.title

    def clean(self):
        errors = {}
        self.title = (self.title or "").strip()

        if not self.title:
            errors["title"] = "Document title cannot be empty."

        if self.document_key:
            self.document_key = self.document_key.strip()

        if self.current_version_id:
            if self.pk is None:
                errors["current_version"] = (
                    "Current version cannot be assigned before the document is created."
                )
            elif self.current_version.document_id != self.pk:
                errors["current_version"] = (
                    "Current version must belong to the same document."
                )

        if errors:
            raise ValidationError(errors)

    def _generate_document_key(self) -> str:
        base_key = slugify(self.title, allow_unicode=True) or "document"
        base_key = base_key[:160]

        candidate = base_key
        suffix = 2
        queryset = type(self).objects.exclude(pk=self.pk)

        while queryset.filter(document_key=candidate).exists():
            suffix_str = f"-{suffix}"
            candidate = f"{base_key[: 160 - len(suffix_str)]}{suffix_str}"
            suffix += 1

        return candidate

    def save(self, *args, **kwargs):
        self.title = (self.title or "").strip()

        if not self.document_key:
            self.document_key = self._generate_document_key()

        self.full_clean(validate_unique=False, validate_constraints=False)
        return super().save(*args, **kwargs)


class DocumentVersion(models.Model):
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="versions",
    )
    version_number = models.PositiveIntegerField()
    source_filename = models.CharField(max_length=255, blank=True)
    source_revision_id = models.CharField(max_length=128, blank=True)
    effective_date = models.DateField(null=True, blank=True)
    file = models.FileField(upload_to=document_version_upload_to)
    file_size = models.PositiveBigIntegerField(default=0)
    content_type = models.CharField(max_length=127, blank=True)
    extracted_text = models.TextField(blank=True)
    normalized_text = models.TextField(blank=True)
    content_hash = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-version_number", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["document", "version_number"],
                name="uniq_document_version_number",
            )
        ]
        indexes = [
            models.Index(fields=["document", "-version_number"]),
            models.Index(fields=["document", "effective_date"]),
            models.Index(fields=["content_hash"]),
        ]

    def __str__(self) -> str:
        return f"{self.document.title} v{self.version_number}"

    def clean(self):
        errors = {}

        self.source_filename = Path((self.source_filename or "").strip()).name
        self.source_revision_id = (self.source_revision_id or "").strip()

        if self.version_number <= 0:
            errors["version_number"] = "Version number must be positive."

        if self.pk:
            original = type(self).objects.filter(pk=self.pk).first()
            if original is not None:
                immutable_fields = {
                    "document": self.document_id != original.document_id,
                    "version_number": self.version_number != original.version_number,
                    "source_filename": self.source_filename != original.source_filename,
                    "source_revision_id": (
                        self.source_revision_id != original.source_revision_id
                    ),
                    "effective_date": self.effective_date != original.effective_date,
                    "file": self.file.name != original.file.name,
                }
                changed_immutable_fields = [
                    field_name
                    for field_name, changed in immutable_fields.items()
                    if changed
                ]
                if changed_immutable_fields:
                    errors["__all__"] = (
                        "Document version identity fields are immutable after creation: "
                        + ", ".join(changed_immutable_fields)
                    )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.file and not self.file_size:
            self.file_size = getattr(self.file, "size", 0) or 0

        self.full_clean(validate_unique=False, validate_constraints=False)
        saved = super().save(*args, **kwargs)

        if self.document_id:
            Document.objects.filter(pk=self.document_id).update(
                current_version=self,
                updated_at=timezone.now(),
            )

            if hasattr(self, "document") and self.document is not None:
                self.document.current_version = self
                self.document.updated_at = timezone.now()

        return saved


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
        constraints = [
            models.UniqueConstraint(
                fields=["version", "chunk_index"],
                name="uniq_chunk_per_version_index",
            )
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


class VersionComparison(DomainValidatedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Черновик"
        COMPLETED = "completed", "Завершено"
        FAILED = "failed", "Ошибка"

    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="comparisons",
    )
    from_version = models.ForeignKey(
        DocumentVersion,
        on_delete=models.CASCADE,
        related_name="comparisons_from",
    )
    to_version = models.ForeignKey(
        DocumentVersion,
        on_delete=models.CASCADE,
        related_name="comparisons_to",
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["from_version", "to_version"],
                name="uniq_version_comparison_pair",
            ),
            models.CheckConstraint(
                condition=~Q(from_version=F("to_version")),
                name="comparison_versions_must_differ",
            ),
        ]

    def clean(self):
        errors = {}

        if self.from_version_id and self.to_version_id:
            if self.from_version_id == self.to_version_id:
                errors["to_version"] = "Comparison requires two different versions."

            if self.from_version.document_id != self.to_version.document_id:
                errors["to_version"] = "Versions must belong to the same document."

            if self.from_version.version_number >= self.to_version.version_number:
                errors["to_version"] = (
                    "Target version must be newer than source version."
                )

            expected_document_id = self.from_version.document_id
            if self.document_id and self.document_id != expected_document_id:
                errors["document"] = "Comparison document must match both versions."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.from_version_id and not self.document_id:
            self.document_id = self.from_version.document_id
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return (
            f"Comparison {self.id}: " f"{self.from_version_id} -> {self.to_version_id}"
        )


class VersionChangeItem(DomainValidatedModel):
    class ChangeType(models.TextChoices):
        ADDED = "added", "Добавлено"
        REMOVED = "removed", "Удалено"
        MODIFIED = "modified", "Изменено"
        MOVED = "moved", "Перемещено"

    comparison = models.ForeignKey(
        VersionComparison,
        on_delete=models.CASCADE,
        related_name="change_items",
    )
    change_type = models.CharField(max_length=16, choices=ChangeType.choices)
    old_chunk = models.ForeignKey(
        Chunk,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="change_items_old",
    )
    new_chunk = models.ForeignKey(
        Chunk,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="change_items_new",
    )
    similarity = models.FloatField(null=True, blank=True)
    match_reason = models.CharField(max_length=128, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "id"]
        indexes = [
            models.Index(fields=["comparison", "change_type"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    (
                        Q(change_type="added")
                        & Q(old_chunk__isnull=True)
                        & Q(new_chunk__isnull=False)
                    )
                    | (
                        Q(change_type="removed")
                        & Q(old_chunk__isnull=False)
                        & Q(new_chunk__isnull=True)
                    )
                    | (
                        Q(change_type__in=["modified", "moved"])
                        & Q(old_chunk__isnull=False)
                        & Q(new_chunk__isnull=False)
                    )
                ),
                name="change_item_chunk_shape_valid",
            )
        ]

    def clean(self):
        errors = {}
        old_version_id = self.old_chunk.version_id if self.old_chunk_id else None
        new_version_id = self.new_chunk.version_id if self.new_chunk_id else None

        if self.change_type == self.ChangeType.ADDED:
            if self.old_chunk_id is not None or self.new_chunk_id is None:
                errors["new_chunk"] = (
                    "Added change items must point only to a chunk in the target version."
                )
        elif self.change_type == self.ChangeType.REMOVED:
            if self.old_chunk_id is None or self.new_chunk_id is not None:
                errors["old_chunk"] = (
                    "Removed change items must point only to a chunk in the source version."
                )
        elif self.change_type in {self.ChangeType.MODIFIED, self.ChangeType.MOVED}:
            if self.old_chunk_id is None or self.new_chunk_id is None:
                errors["new_chunk"] = (
                    "Modified and moved items require both source and target chunks."
                )

        if self.comparison_id:
            if old_version_id and old_version_id != self.comparison.from_version_id:
                errors["old_chunk"] = (
                    "Old chunk must belong to the comparison source version."
                )
            if new_version_id and new_version_id != self.comparison.to_version_id:
                errors["new_chunk"] = (
                    "New chunk must belong to the comparison target version."
                )

        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return (
            f"ChangeItem {self.id} "
            f"[{self.change_type}] comparison={self.comparison_id}"
        )


class Summary(DomainValidatedModel):
    comparison = models.OneToOneField(
        VersionComparison,
        on_delete=models.CASCADE,
        related_name="summary",
    )
    text = models.TextField()
    highlights = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Summary for comparison {self.comparison_id}"


class Employee(models.Model):
    full_name = models.CharField(max_length=255)
    position = models.CharField(max_length=255, blank=True)
    department = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["full_name", "id"]

    def __str__(self) -> str:
        return self.full_name


class GeneratedQuiz(DomainValidatedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Черновик"
        APPROVED = "approved", "Утверждён"
        ARCHIVED = "archived", "Архив"

    comparison = models.ForeignKey(
        VersionComparison,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generated_quizzes",
    )
    summary = models.ForeignKey(
        Summary,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generated_quizzes",
    )
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
    payload = models.JSONField(default=dict, blank=True)
    questions_count = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    approved_by_name = models.CharField(max_length=255, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approval_comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.CheckConstraint(
                condition=~Q(from_version=F("to_version")),
                name="generated_quiz_versions_must_differ",
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(status="approved")
                    | (Q(approved_at__isnull=False) & ~Q(approved_by_name=""))
                ),
                name="generated_quiz_approval_fields_required",
            ),
        ]

    def clean(self):
        errors = {}

        if self.from_version_id and self.to_version_id:
            if self.from_version.document_id != self.to_version.document_id:
                errors["to_version"] = "Quiz versions must belong to the same document."
            if self.from_version.version_number >= self.to_version.version_number:
                errors["to_version"] = (
                    "Quiz target version must be newer than source version."
                )

        if self.summary_id and not self.comparison_id:
            errors["comparison"] = "Summary cannot be attached without a comparison."

        if self.comparison_id:
            if self.comparison.from_version_id != self.from_version_id:
                errors["comparison"] = "Comparison source version does not match quiz."
            if self.comparison.to_version_id != self.to_version_id:
                errors["comparison"] = "Comparison target version does not match quiz."
            if self.summary_id and self.summary.comparison_id != self.comparison_id:
                errors["summary"] = "Summary must belong to the same comparison."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")

        if (
            self.status == self.Status.APPROVED
            and self.approved_at is None
            and self.approved_by_name
        ):
            self.approved_at = timezone.now()

            if update_fields is not None:
                update_fields = set(update_fields)
                update_fields.add("approved_at")
                kwargs["update_fields"] = list(update_fields)

        return super().save(*args, **kwargs)


class Question(models.Model):
    class QuestionType(models.TextChoices):
        SINGLE_CHOICE = "single_choice", "Один вариант"
        MULTIPLE_CHOICE = "multiple_choice", "Несколько вариантов"
        TRUE_FALSE = "true_false", "Верно/Неверно"
        TEXT = "text", "Текстовый ответ"

    quiz = models.ForeignKey(
        GeneratedQuiz,
        on_delete=models.CASCADE,
        related_name="questions",
    )
    source_change_item = models.ForeignKey(
        VersionChangeItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="questions",
    )
    order = models.PositiveIntegerField(default=1)
    question_type = models.CharField(
        max_length=32,
        choices=QuestionType.choices,
        default=QuestionType.SINGLE_CHOICE,
    )
    prompt = models.TextField()
    explanation = models.TextField(blank=True)
    correct_text_answer = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["quiz", "order"],
                name="uniq_question_order_per_quiz",
            )
        ]

    def __str__(self) -> str:
        return f"Question {self.order} for quiz {self.quiz_id}"


class Choice(models.Model):
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="choices",
    )
    order = models.PositiveIntegerField(default=1)
    text = models.TextField()
    is_correct = models.BooleanField(default=False)

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["question", "order"],
                name="uniq_choice_order_per_question",
            )
        ]

    def __str__(self) -> str:
        return f"Choice {self.order} for question {self.question_id}"


class QuizAttempt(DomainValidatedModel):
    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "В процессе"
        COMPLETED = "completed", "Завершён"

    quiz = models.ForeignKey(
        GeneratedQuiz,
        on_delete=models.CASCADE,
        related_name="attempts",
    )
    employee = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quiz_attempts",
    )
    participant_name = models.CharField(max_length=255)
    answers = models.JSONField(default=list, blank=True)
    score = models.PositiveIntegerField(default=0)
    total_questions = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.IN_PROGRESS,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    (Q(status="completed") & Q(completed_at__isnull=False))
                    | (Q(status="in_progress") & Q(completed_at__isnull=True))
                ),
                name="quiz_attempt_status_matches_completion",
            )
        ]

    def save(self, *args, **kwargs):
        if self.status == self.Status.COMPLETED and self.completed_at is None:
            self.completed_at = timezone.now()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"Attempt {self.id} - {self.participant_name}"


class Answer(models.Model):
    attempt = models.ForeignKey(
        QuizAttempt,
        on_delete=models.CASCADE,
        related_name="answer_items",
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="answers",
    )
    selected_choice = models.ForeignKey(
        Choice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="answers",
    )
    text_answer = models.TextField(blank=True)
    is_correct = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["attempt", "question"],
                name="uniq_answer_per_attempt_question",
            )
        ]

    def __str__(self) -> str:
        return f"Answer {self.id} for attempt {self.attempt_id}"
