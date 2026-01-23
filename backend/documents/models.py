# backend/documents/models.py
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
