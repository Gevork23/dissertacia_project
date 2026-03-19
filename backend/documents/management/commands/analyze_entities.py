from __future__ import annotations

from django.core.management.base import BaseCommand

from documents.analysis_service import analyze_version_entities
from documents.models import DocumentVersion


class Command(BaseCommand):
    help = (
        "Run entity extraction for one version or all versions. "
        "Modes: rules, llm, hybrid."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--version-id",
            type=int,
            help="Analyze only one DocumentVersion by id.",
        )
        parser.add_argument(
            "--mode",
            choices=["rules", "llm", "hybrid"],
            default="rules",
            help="Entity extraction mode.",
        )

    def handle(self, *args, **options):
        version_id = options.get("version_id")
        mode = options.get("mode", "rules")

        if version_id:
            versions = DocumentVersion.objects.filter(pk=version_id)
            if not versions.exists():
                self.stdout.write(
                    self.style.ERROR(
                        f"DocumentVersion with id={version_id} was not found."
                    )
                )
                return
        else:
            versions = DocumentVersion.objects.all().order_by("id")

        total_versions = 0
        total_chunks = 0
        total_entities = 0

        for version in versions:
            result = analyze_version_entities(version, mode=mode)
            total_versions += 1
            total_chunks += int(result["chunks_count"])
            total_entities += int(result["entities_count"])

            self.stdout.write(
                self.style.SUCCESS(
                    f'mode={result["extraction_method"]} '
                    f'version_id={result["version_id"]} '
                    f'document_id={result["document_id"]} '
                    f'chunks={result["chunks_count"]} '
                    f'entities={result["entities_count"]}'
                )
            )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Done: mode={mode} versions={total_versions} "
                f"chunks={total_chunks} entities={total_entities}"
            )
        )
