# backend/documents/admin.py
from django.contrib import admin

from .models import Chunk, Document, DocumentVersion


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "updated_at", "created_at")
    search_fields = ("title",)
    ordering = ("-updated_at",)


@admin.register(DocumentVersion)
class DocumentVersionAdmin(admin.ModelAdmin):
    list_display = ("id", "document", "version_number", "created_at")
    list_filter = ("document",)
    ordering = ("-created_at",)


@admin.register(Chunk)
class ChunkAdmin(admin.ModelAdmin):
    list_display = ("id", "version", "chunk_index", "heading")
    list_filter = ("version__document",)
    ordering = ("version", "chunk_index")
