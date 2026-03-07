from __future__ import annotations

from django.core.management.base import BaseCommand

from documents.models import Chunk, DocumentVersion
from documents.qdrant_service import index_chunks
from documents.text_processing import chunk_by_structure_ru, normalize_text, sha256_hex


class Command(BaseCommand):
    help = "Rebuild normalized_text, chunks, and Qdrant index for document versions."

    def add_arguments(self, parser):
        parser.add_argument(
            "--version-id",
            type=int,
            dest="version_id",
            help="Rebuild only one version by id.",
        )

    def handle(self, *args, **options):
        version_id = options.get("version_id")

        queryset = DocumentVersion.objects.all().order_by("id")
        if version_id is not None:
            queryset = queryset.filter(id=version_id)

        total_versions = queryset.count()
        self.stdout.write(f"Found versions: {total_versions}")

        for version in queryset:
            normalized = normalize_text(version.extracted_text or "")
            version.normalized_text = normalized
            version.content_hash = sha256_hex(normalized)
            version.save(update_fields=["normalized_text", "content_hash"])

            deleted_count, _ = version.chunks.all().delete()

            chunks = chunk_by_structure_ru(normalized)
            created_count = 0

            for chunk in chunks:
                Chunk.objects.create(
                    version=version,
                    chunk_index=chunk.chunk_index,
                    heading=chunk.heading,
                    section_path=chunk.section_path,
                    text=chunk.text,
                    text_hash=chunk.text_hash,
                )
                created_count += 1

            indexed_count = index_chunks(version.id)

            self.stdout.write(
                self.style.SUCCESS(
                    f"Version {version.id}: "
                    f"deleted_chunks={deleted_count}, "
                    f"created_chunks={created_count}, "
                    f"indexed_chunks={indexed_count}"
                )
            )

        self.stdout.write(self.style.SUCCESS("Rebuild complete."))
