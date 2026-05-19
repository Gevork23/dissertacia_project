from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone
from django.utils.text import slugify

ALLOWED_DOCUMENT_EXTENSIONS = {".txt", ".pdf", ".docx", ".xml"}


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
    class FragmentType(models.TextChoices):
        TITLE = "title", "Заголовок"
        PREAMBLE = "preamble", "Преамбула"
        SECTION = "section", "Раздел"
        CHAPTER = "chapter", "Глава"
        ARTICLE = "article", "Статья"
        POINT = "point", "Пункт"
        SUBPOINT = "subpoint", "Подпункт"
        PARAGRAPH = "paragraph", "Абзац"
        FALLBACK_BLOCK = "fallback_block", "Fallback-блок"

    version = models.ForeignKey(
        DocumentVersion,
        on_delete=models.CASCADE,
        related_name="chunks",
    )
    chunk_index = models.PositiveIntegerField()
    fragment_type = models.CharField(
        max_length=32,
        choices=FragmentType.choices,
        default=FragmentType.FALLBACK_BLOCK,
    )
    structure_level = models.PositiveSmallIntegerField(default=0)
    raw_label = models.CharField(max_length=255, blank=True)
    canonical_label = models.CharField(max_length=255, blank=True)
    path_key = models.CharField(max_length=512, blank=True)
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
            models.Index(fields=["version", "fragment_type"]),
            models.Index(fields=["version", "path_key"]),
            models.Index(fields=["text_hash"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["version", "chunk_index"],
                name="uniq_chunk_per_version_index",
            )
        ]

    def __str__(self) -> str:
        return f"Chunk {self.chunk_index} [{self.fragment_type}] ({self.version})"


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

    class ComparisonUnit(models.TextChoices):
        CHUNK = "chunk", "Структурный фрагмент"
        DOCUMENT_TEXT = "document_text", "Документ целиком"

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
    comparison_unit = models.CharField(
        max_length=32,
        choices=ComparisonUnit.choices,
        default=ComparisonUnit.CHUNK,
    )
    matching_strategy = models.CharField(max_length=64, default="structural_chunks_v2")
    identical = models.BooleanField(default=False)
    added_count = models.PositiveIntegerField(default=0)
    removed_count = models.PositiveIntegerField(default=0)
    modified_count = models.PositiveIntegerField(default=0)
    moved_count = models.PositiveIntegerField(default=0)
    unchanged_count = models.PositiveIntegerField(default=0)
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

    class SemanticType(models.TextChoices):
        DEADLINE = "deadline", "Сроки"
        DOCUMENT = "document", "Документы"
        OBLIGATION = "obligation", "Обязанности"
        PROCEDURE = "procedure", "Процедура"
        REFUSAL = "refusal", "Основания отказа"
        CONDITION = "condition", "Условия"
        RESPONSIBILITY = "responsibility", "Ответственность"
        INFORMATIONAL = "informational", "Информационное"
        EDITORIAL = "editorial", "Редакционное"
        STRUCTURE = "structure", "Структурное"
        UNCLASSIFIED = "unclassified", "Не классифицировано"

    class SignificanceLabel(models.TextChoices):
        CRITICAL = "critical", "Критично"
        IMPORTANT = "important", "Важно"
        INFORMATIONAL = "informational", "Информационно"
        EDITORIAL = "editorial", "Редакционно"
        NOT_EVALUATED = "not_evaluated", "Не оценено"

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
    old_text = models.TextField(blank=True, default="")
    new_text = models.TextField(blank=True, default="")
    similarity = models.FloatField(null=True, blank=True)
    match_reason = models.CharField(max_length=128, blank=True)
    semantic_type = models.CharField(
        max_length=32,
        choices=SemanticType.choices,
        default=SemanticType.UNCLASSIFIED,
    )
    extracted_entities = models.JSONField(default=list, blank=True)
    significance_label = models.CharField(
        max_length=32,
        choices=SignificanceLabel.choices,
        default=SignificanceLabel.NOT_EVALUATED,
    )
    significance_score = models.FloatField(default=0.0)
    significance_reason = models.TextField(blank=True, default="")
    significance_rules = models.JSONField(default=list, blank=True)
    requires_manual_review = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "id"]
        indexes = [
            models.Index(fields=["comparison", "change_type"]),
            models.Index(fields=["comparison", "semantic_type"]),
            models.Index(fields=["comparison", "significance_label"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    (
                        Q(change_type="added")
                        & Q(old_chunk__isnull=True)
                        & Q(old_text="")
                        & (Q(new_chunk__isnull=False) | ~Q(new_text=""))
                    )
                    | (
                        Q(change_type="removed")
                        & (Q(old_chunk__isnull=False) | ~Q(old_text=""))
                        & Q(new_chunk__isnull=True)
                        & Q(new_text="")
                    )
                    | (
                        Q(change_type__in=["modified", "moved"])
                        & (Q(old_chunk__isnull=False) | ~Q(old_text=""))
                        & (Q(new_chunk__isnull=False) | ~Q(new_text=""))
                    )
                ),
                name="change_item_payload_shape_valid",
            ),
            models.CheckConstraint(
                condition=Q(significance_score__gte=0.0)
                & Q(significance_score__lte=1.0),
                name="change_item_significance_score_range_valid",
            ),
        ]

    def clean(self):
        errors = {}
        old_version_id = self.old_chunk.version_id if self.old_chunk_id else None
        new_version_id = self.new_chunk.version_id if self.new_chunk_id else None
        old_text = (self.old_text or "").strip()
        new_text = (self.new_text or "").strip()
        has_old_payload = self.old_chunk_id is not None or bool(old_text)
        has_new_payload = self.new_chunk_id is not None or bool(new_text)

        if self.change_type == self.ChangeType.ADDED:
            if self.old_chunk_id is not None or old_text:
                errors["old_chunk"] = (
                    "Added change items must not contain a source chunk or source text."
                )
            if not has_new_payload:
                errors["new_chunk"] = (
                    "Added change items must contain target chunk data or target text."
                )
        elif self.change_type == self.ChangeType.REMOVED:
            if self.new_chunk_id is not None or new_text:
                errors["new_chunk"] = (
                    "Removed change items must not contain a target chunk or target text."
                )
            if not has_old_payload:
                errors["old_chunk"] = (
                    "Removed change items must contain source chunk data or source text."
                )
        elif self.change_type in {self.ChangeType.MODIFIED, self.ChangeType.MOVED}:
            if not has_old_payload or not has_new_payload:
                errors["new_chunk"] = (
                    "Modified and moved items require source and target chunk data or text snapshots."
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

        semantic_type = self.semantic_type or self.SemanticType.UNCLASSIFIED
        if semantic_type not in self.SemanticType.values:
            errors["semantic_type"] = "Unknown semantic type for change item."

        significance_label = (
            self.significance_label or self.SignificanceLabel.NOT_EVALUATED
        )
        if significance_label not in self.SignificanceLabel.values:
            errors["significance_label"] = "Unknown significance label for change item."

        try:
            significance_score = float(self.significance_score or 0.0)
        except (TypeError, ValueError):
            errors["significance_score"] = "Significance score must be numeric."
        else:
            if significance_score < 0.0 or significance_score > 1.0:
                errors["significance_score"] = (
                    "Significance score must be between 0.0 and 1.0."
                )

        if self.extracted_entities is not None and not isinstance(
            self.extracted_entities, list
        ):
            errors["extracted_entities"] = (
                "Extracted entities must be stored as a list."
            )

        if self.significance_rules is not None and not isinstance(
            self.significance_rules, list
        ):
            errors["significance_rules"] = (
                "Significance rules must be stored as a list."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.old_chunk_id and not self.old_text:
            self.old_text = self.old_chunk.text
        if self.new_chunk_id and not self.new_text:
            self.new_text = self.new_chunk.text
        if not self.semantic_type:
            self.semantic_type = self.SemanticType.UNCLASSIFIED
        if not self.significance_label:
            self.significance_label = self.SignificanceLabel.NOT_EVALUATED
        if self.significance_score is None:
            self.significance_score = 0.0
        if self.extracted_entities is None:
            self.extracted_entities = []
        if self.significance_rules is None:
            self.significance_rules = []
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return (
            f"ChangeItem {self.id} "
            f"[{self.change_type}/{self.significance_label}] comparison={self.comparison_id}"
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
        PENDING_REVIEW = "pending_review", "На проверке"
        APPROVED = "approved", "Утверждён"
        REJECTED = "rejected", "Отклонён"
        SUPERSEDED = "superseded", "Заменён"
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
        max_length=24,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    submitted_for_review_at = models.DateTimeField(null=True, blank=True)
    approved_by_name = models.CharField(max_length=255, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approval_comment = models.TextField(blank=True)
    rejected_by_name = models.CharField(max_length=255, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejection_comment = models.TextField(blank=True)
    superseded_at = models.DateTimeField(null=True, blank=True)
    superseded_reason = models.TextField(blank=True)
    llm_error_analysis = models.TextField(blank=True)
    llm_manager_summary = models.TextField(blank=True)
    llm_reporting_cache_key = models.CharField(max_length=64, blank=True)
    llm_reporting_model = models.CharField(max_length=128, blank=True)
    llm_reporting_generated_at = models.DateTimeField(null=True, blank=True)
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
            models.CheckConstraint(
                condition=(
                    ~Q(status="pending_review")
                    | Q(submitted_for_review_at__isnull=False)
                ),
                name="generated_quiz_review_submission_timestamp_required",
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(status="rejected")
                    | (Q(rejected_at__isnull=False) & ~Q(rejected_by_name=""))
                ),
                name="generated_quiz_rejection_fields_required",
            ),
            models.CheckConstraint(
                condition=(~Q(status="superseded") | Q(superseded_at__isnull=False)),
                name="generated_quiz_superseded_timestamp_required",
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
            self.status == self.Status.PENDING_REVIEW
            and self.submitted_for_review_at is None
        ):
            self.submitted_for_review_at = timezone.now()
            if update_fields is not None:
                update_fields = set(update_fields)
                update_fields.add("submitted_for_review_at")
                kwargs["update_fields"] = list(update_fields)

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

        if (
            self.status == self.Status.REJECTED
            and self.rejected_at is None
            and self.rejected_by_name
        ):
            self.rejected_at = timezone.now()
            if update_fields is not None:
                update_fields = set(update_fields)
                update_fields.add("rejected_at")
                kwargs["update_fields"] = list(update_fields)

        if self.status == self.Status.SUPERSEDED and self.superseded_at is None:
            self.superseded_at = timezone.now()
            if update_fields is not None:
                update_fields = set(update_fields)
                update_fields.add("superseded_at")
                kwargs["update_fields"] = list(update_fields)

        return super().save(*args, **kwargs)


class QuizAssignment(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="quiz_assignments",
    )
    quiz = models.ForeignKey(
        GeneratedQuiz,
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="granted_quiz_assignments",
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-assigned_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "quiz"],
                name="uniq_quiz_assignment_per_user",
            )
        ]

    def clean(self):
        errors = {}
        if self.quiz_id and self.quiz.status != GeneratedQuiz.Status.APPROVED:
            errors["quiz"] = "Only approved quizzes can be assigned to employees."
        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return f"{self.user} -> quiz {self.quiz_id}"


class ModeratedChange(models.Model):
    class Label(models.TextChoices):
        CRITICAL = "critical", "Critical"
        IMPORTANT = "important", "Important"
        MINOR = "minor", "Minor"
        IGNORED = "ignored", "Ignored"

    from_version = models.ForeignKey(
        "DocumentVersion",
        on_delete=models.CASCADE,
        related_name="moderated_from",
    )
    to_version = models.ForeignKey(
        "DocumentVersion",
        on_delete=models.CASCADE,
        related_name="moderated_to",
    )
    change_id = models.CharField(max_length=64)
    original_label = models.CharField(max_length=32, choices=Label.choices)
    corrected_label = models.CharField(max_length=32, choices=Label.choices)
    comment = models.TextField(blank=True)
    moderated_at = models.DateTimeField(auto_now_add=True)
    moderated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="moderated_changes",
    )

    class Meta:
        ordering = ["-moderated_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["from_version", "to_version", "change_id"],
                name="uniq_moderated_change_per_pair_and_change",
            ),
            models.CheckConstraint(
                condition=~Q(from_version=F("to_version")),
                name="moderated_change_versions_must_differ",
            ),
        ]
        indexes = [
            models.Index(fields=["from_version", "to_version"]),
            models.Index(fields=["change_id"]),
        ]

    def clean(self):
        errors = {}
        if self.from_version_id and self.to_version_id:
            if self.from_version.document_id != self.to_version.document_id:
                errors["to_version"] = "Moderated versions must belong to the same document."
            if self.from_version.version_number >= self.to_version.version_number:
                errors["to_version"] = "Moderated target version must be newer than source version."
        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return (
            f"ModeratedChange {self.change_id} "
            f"{self.from_version_id}->{self.to_version_id} "
            f"{self.original_label}->{self.corrected_label}"
        )


class GoldChangeAnnotation(models.Model):
    class Relevance(models.TextChoices):
        RELEVANT = "relevant", "Relevant"
        NOT_RELEVANT = "not_relevant", "Not relevant"
        UNKNOWN = "unknown", "Unknown"

    change_item = models.ForeignKey(
        VersionChangeItem,
        on_delete=models.CASCADE,
        related_name="gold_annotations",
    )
    annotator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gold_change_annotations",
    )
    corrected_semantic_type = models.CharField(
        max_length=32,
        choices=VersionChangeItem.SemanticType.choices,
        blank=True,
    )
    corrected_significance_label = models.CharField(
        max_length=32,
        choices=VersionChangeItem.SignificanceLabel.choices,
        blank=True,
    )
    corrected_requires_manual_review = models.BooleanField(null=True, blank=True)
    relevance = models.CharField(
        max_length=16,
        choices=Relevance.choices,
        default=Relevance.UNKNOWN,
    )
    is_false_positive = models.BooleanField(default=False)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["change_item", "annotator"],
                name="uniq_gold_change_annotation_per_user",
            )
        ]
        indexes = [
            models.Index(fields=["change_item", "annotator"]),
        ]

    def __str__(self) -> str:
        return f"GoldChangeAnnotation change={self.change_item_id} annotator={self.annotator_id}"


class GoldSummaryAnnotation(models.Model):
    class QualityLabel(models.TextChoices):
        GOOD = "good", "Good"
        PARTIALLY_CORRECT = "partially_correct", "Partially correct"
        UNSUPPORTED = "unsupported", "Unsupported"
        MISSING_KEY_POINT = "missing_key_point", "Missing key point"
        OVEREMPHASIZED_NOISE = "overemphasized_noise", "Overemphasized noise"

    summary = models.ForeignKey(
        Summary,
        on_delete=models.CASCADE,
        related_name="gold_annotations",
    )
    source_change_item = models.ForeignKey(
        VersionChangeItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gold_summary_annotations",
    )
    annotator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gold_summary_annotations",
    )
    highlight_index = models.PositiveIntegerField(null=True, blank=True)
    quality_label = models.CharField(max_length=32, choices=QualityLabel.choices)
    corrected_text = models.TextField(blank=True)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["summary", "annotator", "highlight_index"],
                name="uniq_gold_summary_annotation_per_user_and_highlight",
            )
        ]
        indexes = [
            models.Index(fields=["summary", "annotator"]),
            models.Index(fields=["source_change_item"]),
        ]

    def __str__(self) -> str:
        return f"GoldSummaryAnnotation summary={self.summary_id} highlight={self.highlight_index}"


class GoldQuizAnnotation(models.Model):
    class QualityLabel(models.TextChoices):
        GOOD = "good", "Good"
        PARTIALLY_CORRECT = "partially_correct", "Partially correct"
        INCORRECT = "incorrect", "Incorrect"
        IRRELEVANT = "irrelevant", "Irrelevant"
        AMBIGUOUS = "ambiguous", "Ambiguous"
        UNSUPPORTED = "unsupported", "Unsupported"

    question = models.ForeignKey(
        "Question",
        on_delete=models.CASCADE,
        related_name="gold_annotations",
    )
    annotator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gold_quiz_annotations",
    )
    quality_label = models.CharField(max_length=32, choices=QualityLabel.choices)
    corrected_question_text = models.TextField(blank=True)
    corrected_explanation = models.TextField(blank=True)
    should_keep = models.BooleanField(default=True)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["question", "annotator"],
                name="uniq_gold_quiz_annotation_per_user",
            )
        ]
        indexes = [
            models.Index(fields=["question", "annotator"]),
        ]

    def __str__(self) -> str:
        return f"GoldQuizAnnotation question={self.question_id} annotator={self.annotator_id}"


class RusLawODDocument(models.Model):
    pravo_gov_ru_nd = models.CharField(max_length=64, unique=True, db_index=True)
    heading = models.CharField(max_length=4096, verbose_name="Заголовок документа",blank=True)
    document_date = models.DateField(null=True, blank=True)
    source_xml = models.TextField()
    cleaned_text = models.TextField(blank=True, null=True, verbose_name="Очищенный текст")
    version_family_key = models.CharField(max_length=255, blank=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    imported_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["version_family_key", "document_date", "pravo_gov_ru_nd"]
        indexes = [
            models.Index(fields=["version_family_key", "document_date"]),
        ]

    def clean(self):
        errors = {}
        self.pravo_gov_ru_nd = (self.pravo_gov_ru_nd or "").strip()
        self.heading = " ".join((self.heading or "").split())
        self.cleaned_text = " ".join((self.cleaned_text or "").split())
        self.version_family_key = (self.version_family_key or "").strip()

        if not self.pravo_gov_ru_nd:
            errors["pravo_gov_ru_nd"] = "pravo.gov.ru identifier cannot be empty."
        if not self.source_xml:
            errors["source_xml"] = "Source XML cannot be empty."
        if not self.cleaned_text:
            errors["cleaned_text"] = "Cleaned text cannot be empty."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean(validate_unique=False, validate_constraints=False)
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        title = self.heading or self.pravo_gov_ru_nd
        return f"RusLawOD {title}"


class ManualDocument(models.Model):
    title = models.CharField(max_length=255)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="manual_documents",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    file = models.FileField(upload_to="manual_uploads/%Y/%m/%d/", blank=True, null=True)
    extracted_text = models.TextField()
    version = models.PositiveIntegerField(default=1)
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="manual_uploads",
    )
    document_version = models.ForeignKey(
        DocumentVersion,
        on_delete=models.CASCADE,
        related_name="manual_uploads",
    )

    class Meta:
        ordering = ["-uploaded_at", "-id"]

    def clean(self):
        errors = {}
        self.title = " ".join((self.title or "").split())
        self.extracted_text = " ".join((self.extracted_text or "").split())

        if not self.title:
            errors["title"] = "Manual document title cannot be empty."
        if not self.extracted_text:
            errors["extracted_text"] = "Extracted text cannot be empty."
        if self.document_version_id and self.document_id:
            if self.document_version.document_id != self.document_id:
                errors["document_version"] = (
                    "Manual document version must belong to the selected document."
                )
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean(validate_unique=False, validate_constraints=False)
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.title} v{self.version}"


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
    answered_questions = models.PositiveIntegerField(default=0)
    correct_answers = models.PositiveIntegerField(default=0)
    score_percent = models.FloatField(default=0.0)
    llm_feedback = models.TextField(blank=True)
    llm_feedback_cache_key = models.CharField(max_length=64, blank=True)
    llm_feedback_model = models.CharField(max_length=128, blank=True)
    llm_feedback_generated_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.IN_PROGRESS,
    )
    started_at = models.DateTimeField(default=timezone.now)
    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    (
                        Q(status="completed")
                        & Q(submitted_at__isnull=False)
                        & Q(completed_at__isnull=False)
                    )
                    | (
                        Q(status="in_progress")
                        & Q(submitted_at__isnull=True)
                        & Q(completed_at__isnull=True)
                    )
                ),
                name="quiz_attempt_status_matches_completion",
            ),
            models.UniqueConstraint(
                fields=["quiz", "participant_name"],
                condition=Q(status="in_progress"),
                name="uniq_active_attempt_per_quiz_participant",
            ),
        ]

    def clean(self):
        errors = {}
        self.participant_name = " ".join((self.participant_name or "").strip().split())

        if not self.participant_name:
            errors["participant_name"] = "Participant name cannot be empty."

        if self.answered_questions > self.total_questions:
            errors["answered_questions"] = (
                "Answered questions cannot exceed the total number of questions."
            )

        if self.correct_answers > self.answered_questions:
            errors["correct_answers"] = (
                "Correct answers cannot exceed the number of answered questions."
            )

        if self.score != self.correct_answers:
            errors["score"] = "Score must match the number of correct answers."

        if self.score_percent < 0 or self.score_percent > 100:
            errors["score_percent"] = "Score percent must be between 0 and 100."

        if self.status == self.Status.COMPLETED:
            if self.submitted_at is None or self.completed_at is None:
                errors["submitted_at"] = (
                    "Completed attempt must have submission timestamps."
                )
        elif self.status == self.Status.IN_PROGRESS:
            if self.submitted_at is not None or self.completed_at is not None:
                errors["submitted_at"] = (
                    "In-progress attempt cannot have completion timestamps."
                )

        if self.pk:
            original = type(self).objects.filter(pk=self.pk).first()
            if original is not None and original.status == self.Status.COMPLETED:
                immutable_fields = {
                    "quiz": self.quiz_id != original.quiz_id,
                    "employee": self.employee_id != original.employee_id,
                    "participant_name": self.participant_name
                    != original.participant_name,
                    "answers": self.answers != original.answers,
                    "score": self.score != original.score,
                    "total_questions": self.total_questions != original.total_questions,
                    "answered_questions": self.answered_questions
                    != original.answered_questions,
                    "correct_answers": self.correct_answers != original.correct_answers,
                    "score_percent": self.score_percent != original.score_percent,
                    "status": self.status != original.status,
                    "started_at": self.started_at != original.started_at,
                    "submitted_at": self.submitted_at != original.submitted_at,
                    "completed_at": self.completed_at != original.completed_at,
                }
                if any(immutable_fields.values()):
                    errors["__all__"] = "Completed attempt is immutable."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")

        self.participant_name = " ".join((self.participant_name or "").strip().split())

        if self.started_at is None:
            self.started_at = timezone.now()
            if update_fields is not None:
                update_fields = set(update_fields)
                update_fields.add("started_at")

        if self.status == self.Status.COMPLETED:
            timestamp = self.submitted_at or timezone.now()
            if self.submitted_at is None:
                self.submitted_at = timestamp
                if update_fields is not None:
                    update_fields = set(update_fields)
                    update_fields.add("submitted_at")
            if self.completed_at is None:
                self.completed_at = timestamp
                if update_fields is not None:
                    update_fields = set(update_fields)
                    update_fields.add("completed_at")
        elif self.status == self.Status.IN_PROGRESS:
            self.submitted_at = None
            self.completed_at = None
            if update_fields is not None:
                update_fields = set(update_fields)
                update_fields.update({"submitted_at", "completed_at"})

        if update_fields is not None:
            kwargs["update_fields"] = list(update_fields)

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

    def clean(self):
        errors = {}

        if self.attempt_id and self.question_id:
            if self.question.quiz_id != self.attempt.quiz_id:
                errors["question"] = (
                    "Answer question must belong to the same quiz as the attempt."
                )

        if self.selected_choice_id and self.question_id:
            if self.selected_choice.question_id != self.question_id:
                errors["selected_choice"] = (
                    "Selected choice must belong to the same question."
                )

        if self.attempt_id and self.attempt.status == QuizAttempt.Status.COMPLETED:
            if self.pk is None:
                errors["attempt"] = "Cannot add answers to a completed attempt."
            else:
                original = type(self).objects.filter(pk=self.pk).first()
                if original is not None:
                    immutable_fields = {
                        "attempt": self.attempt_id != original.attempt_id,
                        "question": self.question_id != original.question_id,
                        "selected_choice": self.selected_choice_id
                        != original.selected_choice_id,
                        "text_answer": self.text_answer != original.text_answer,
                        "is_correct": self.is_correct != original.is_correct,
                    }
                    if any(immutable_fields.values()):
                        errors["__all__"] = (
                            "Answers of a completed attempt are immutable."
                        )

        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return f"Answer {self.id} for attempt {self.attempt_id}"
