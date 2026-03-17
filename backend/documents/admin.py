from django.contrib import admin

from .models import (
    Chunk,
    ChunkAnalysis,
    Document,
    DocumentVersion,
    GeneratedQuiz,
    QuizAttempt,
)


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "updated_at", "created_at")
    search_fields = ("title",)
    ordering = ("-updated_at",)


@admin.register(DocumentVersion)
class DocumentVersionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "document",
        "version_number",
        "source_filename",
        "created_at",
    )
    list_filter = ("document",)
    search_fields = ("document__title", "source_filename")
    ordering = ("-created_at",)


@admin.register(Chunk)
class ChunkAdmin(admin.ModelAdmin):
    list_display = ("id", "version", "chunk_index", "heading")
    list_filter = ("version__document",)
    search_fields = ("heading", "section_path", "text")
    ordering = ("version", "chunk_index")


@admin.register(ChunkAnalysis)
class ChunkAnalysisAdmin(admin.ModelAdmin):
    list_display = ("id", "chunk", "extraction_method", "entities_count", "updated_at")
    list_filter = ("extraction_method",)
    ordering = ("-updated_at",)


@admin.register(GeneratedQuiz)
class GeneratedQuizAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "from_version",
        "to_version",
        "questions_count",
        "created_at",
    )
    list_filter = ("created_at",)
    search_fields = ("title",)
    ordering = ("-created_at",)


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "quiz",
        "participant_name",
        "score",
        "total_questions",
        "created_at",
    )
    list_filter = ("created_at",)
    search_fields = ("participant_name",)
    ordering = ("-created_at",)
