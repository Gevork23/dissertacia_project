from django.contrib import admin
from django.db.models import Count, Max

from .models import (
    Answer,
    Choice,
    Chunk,
    ChunkAnalysis,
    Document,
    DocumentVersion,
    Employee,
    GeneratedQuiz,
    Question,
    QuizAttempt,
    Summary,
    VersionChangeItem,
    VersionComparison,
)


class DocumentVersionInline(admin.TabularInline):
    model = DocumentVersion
    extra = 0
    can_delete = False
    show_change_link = True
    fields = (
        "version_number",
        "source_filename",
        "source_revision_id",
        "effective_date",
        "file",
        "file_size",
        "content_type",
        "created_at",
    )
    readonly_fields = (
        "version_number",
        "source_filename",
        "source_revision_id",
        "effective_date",
        "file",
        "file_size",
        "content_type",
        "created_at",
    )

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "document_key",
        "title",
        "current_version_link",
        "versions_count",
        "latest_version_number",
        "updated_at",
        "created_at",
    )
    search_fields = ("title", "document_key")
    ordering = ("-updated_at",)
    readonly_fields = ("document_key", "current_version")
    inlines = [DocumentVersionInline]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("current_version")
            .annotate(
                versions_count_value=Count("versions"),
                latest_version_number_value=Max("versions__version_number"),
            )
        )

    @admin.display(description="Текущая версия")
    def current_version_link(self, obj):
        if not obj.current_version_id:
            return "—"
        return f"v{obj.current_version.version_number} (id={obj.current_version_id})"

    @admin.display(description="Версий")
    def versions_count(self, obj):
        return obj.versions_count_value

    @admin.display(description="Последняя версия")
    def latest_version_number(self, obj):
        return obj.latest_version_number_value


@admin.register(DocumentVersion)
class DocumentVersionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "document",
        "version_number",
        "source_filename",
        "source_revision_id",
        "effective_date",
        "file_size",
        "content_type",
        "has_extracted_text",
        "created_at",
    )
    list_filter = ("document", "content_type")
    search_fields = (
        "document__title",
        "document__document_key",
        "source_filename",
        "source_revision_id",
        "content_hash",
        "extracted_text",
    )
    ordering = ("document", "-version_number")
    readonly_fields = (
        "document",
        "version_number",
        "source_filename",
        "source_revision_id",
        "effective_date",
        "file",
        "file_size",
        "content_type",
        "content_hash",
        "extracted_text",
        "normalized_text",
        "created_at",
    )
    fields = (
        "document",
        "version_number",
        "source_filename",
        "source_revision_id",
        "effective_date",
        "file",
        "file_size",
        "content_type",
        "content_hash",
        "extracted_text",
        "normalized_text",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    @admin.display(boolean=True, description="Текст извлечён")
    def has_extracted_text(self, obj):
        return bool(obj.extracted_text)


@admin.register(Chunk)
class ChunkAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "version",
        "chunk_index",
        "fragment_type",
        "canonical_label",
        "heading",
    )
    list_filter = ("version__document", "fragment_type")
    search_fields = (
        "heading",
        "canonical_label",
        "raw_label",
        "path_key",
        "section_path",
        "text",
    )
    ordering = ("version", "chunk_index")


@admin.register(ChunkAnalysis)
class ChunkAnalysisAdmin(admin.ModelAdmin):
    list_display = ("id", "chunk", "extraction_method", "entities_count", "updated_at")
    list_filter = ("extraction_method",)
    ordering = ("-updated_at",)


class VersionChangeItemInline(admin.TabularInline):
    model = VersionChangeItem
    extra = 0
    fields = (
        "sort_order",
        "change_type",
        "semantic_type",
        "significance_label",
        "requires_manual_review",
        "old_chunk",
        "new_chunk",
        "old_text",
        "new_text",
        "similarity",
        "match_reason",
    )
    readonly_fields = (
        "semantic_type",
        "significance_label",
        "requires_manual_review",
    )


@admin.register(VersionComparison)
class VersionComparisonAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "document",
        "from_version",
        "to_version",
        "status",
        "comparison_unit",
        "identical",
        "modified_count",
        "added_count",
        "removed_count",
        "created_at",
    )
    list_filter = ("status", "document")
    search_fields = ("document__title",)
    ordering = ("-created_at",)
    inlines = [VersionChangeItemInline]


@admin.register(VersionChangeItem)
class VersionChangeItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "comparison",
        "change_type",
        "semantic_type",
        "significance_label",
        "requires_manual_review",
        "old_chunk",
        "new_chunk",
        "sort_order",
        "match_reason",
    )
    list_filter = (
        "change_type",
        "semantic_type",
        "significance_label",
        "requires_manual_review",
    )
    ordering = ("comparison", "sort_order", "id")


@admin.register(Summary)
class SummaryAdmin(admin.ModelAdmin):
    list_display = ("id", "comparison", "created_at", "updated_at")
    search_fields = ("comparison__document__title", "text")
    ordering = ("-created_at",)


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("id", "full_name", "position", "department", "is_active")
    list_filter = ("is_active", "department")
    search_fields = ("full_name", "position", "department", "email")
    ordering = ("full_name", "id")


class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 0
    fields = ("order", "text", "is_correct")


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 0
    fields = (
        "order",
        "question_type",
        "prompt",
        "correct_text_answer",
        "source_change_item",
    )
    show_change_link = True


@admin.register(GeneratedQuiz)
class GeneratedQuizAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "comparison",
        "from_version",
        "to_version",
        "status",
        "questions_count",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("title", "approved_by_name")
    ordering = ("-created_at",)
    inlines = [QuestionInline]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "quiz", "order", "question_type")
    list_filter = ("question_type",)
    ordering = ("quiz", "order", "id")
    inlines = [ChoiceInline]


@admin.register(Choice)
class ChoiceAdmin(admin.ModelAdmin):
    list_display = ("id", "question", "order", "is_correct")
    list_filter = ("is_correct",)
    ordering = ("question", "order", "id")


class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 0
    fields = ("question", "selected_choice", "text_answer", "is_correct")
    readonly_fields = ("question", "selected_choice", "text_answer", "is_correct")


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "quiz",
        "participant_name",
        "score",
        "total_questions",
        "status",
        "created_at",
        "completed_at",
    )
    list_filter = ("status",)
    search_fields = ("participant_name", "employee__full_name")
    ordering = ("-created_at",)
    inlines = [AnswerInline]


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ("id", "attempt", "question", "is_correct", "created_at")
    list_filter = ("is_correct",)
    ordering = ("attempt", "id")
