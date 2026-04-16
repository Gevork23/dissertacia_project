from __future__ import annotations

from django.core.management.base import BaseCommand
from documents.models import DocumentVersion
from documents.services.ingestion import (
    rebuild_version_chunks,
    safe_index_version_chunks,
)


class Command(BaseCommand):
    help = (
        "Rebuild extracted_text, normalized_text, chunks, and Qdrant index "
        "for document versions."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--version-id",
            type=int,
            dest="version_id",
            help="Rebuild only one version by id.",
        )
        parser.add_argument(
            "--skip-index",
            action="store_true",
            dest="skip_index",
            help="Skip optional Qdrant reindexing step.",
        )

    def handle(self, *args, **options):
        version_id = options.get("version_id")
        skip_index = options.get("skip_index", False)

        queryset = DocumentVersion.objects.all().order_by("id")
        if version_id is not None:
            queryset = queryset.filter(id=version_id)

        total_versions = queryset.count()
        self.stdout.write(f"Found versions: {total_versions}")

        for version in queryset:
            deleted_count = version.chunks.count()
            created_count = rebuild_version_chunks(
                version,
                reindex=False,
                rematerialize_text=True,
            )
            indexed_count = 0 if skip_index else safe_index_version_chunks(version)

            self.stdout.write(
                self.style.SUCCESS(
                    f"Version {version.id}: "
                    f"deleted_chunks={deleted_count}, "
                    f"created_chunks={created_count}, "
                    f"indexed_chunks={indexed_count}"
                )
            )

        self.stdout.write(self.style.SUCCESS("Rebuild complete."))
