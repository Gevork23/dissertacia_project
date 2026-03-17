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


class VersionComparison(models.Model):
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
            )
        ]

    def __str__(self) -> str:
        return (
            f"Comparison {self.id}: "
            f"{self.from_version_id} -> {self.to_version_id}"
        )


class VersionChangeItem(models.Model):
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

    def __str__(self) -> str:
        return (
            f"ChangeItem {self.id} "
            f"[{self.change_type}] comparison={self.comparison_id}"
        )


class Summary(models.Model):
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


class GeneratedQuiz(models.Model):
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
    payload = models.JSONField(default=dict)
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

    def __str__(self):
        return (
            f"Quiz {self.id}: "
            f"{self.from_version_id} -> {self.to_version_id} "
            f"({self.questions_count} questions)"
        )


class Question(models.Model):
    class QuestionType(models.TextChoices):
        OPEN_TEXT = "open_text", "Открытый ответ"
        SINGLE_CHOICE = "single_choice", "Один вариант"

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
    order = models.PositiveIntegerField(default=0)
    question_type = models.CharField(
        max_length=32,
        choices=QuestionType.choices,
        default=QuestionType.OPEN_TEXT,
    )
    prompt = models.TextField()
    correct_text_answer = models.TextField(blank=True)
    explanation = models.TextField(blank=True)
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
    order = models.PositiveIntegerField(default=0)
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


class QuizAttempt(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "В процессе"
        COMPLETED = "completed", "Завершена"

    quiz = models.ForeignKey(
        "GeneratedQuiz",
        on_delete=models.CASCADE,
        related_name="attempts",
    )
    employee = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attempts",
    )
    participant_name = models.CharField(max_length=255, blank=True)
    answers = models.JSONField(default=list)
    score = models.PositiveIntegerField(default=0)
    total_questions = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.COMPLETED,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return (
            f"Attempt {self.id} for quiz {self.quiz_id}: "
            f"{self.score}/{self.total_questions}"
        )


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
                name="uniq_attempt_question_answer",
            )
        ]

    def __str__(self) -> str:
        return f"Answer attempt={self.attempt_id} question={self.question_id}"
