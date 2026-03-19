from __future__ import annotations

from django.core.management.base import BaseCommand
from documents.domain.diff import build_version_diff
from documents.models import DocumentVersion


class Command(BaseCommand):
    help = "Find version pairs of the same document that actually contain changes."

    def handle(self, *args, **options):
        versions = list(
            DocumentVersion.objects.select_related("document")
            .prefetch_related("chunks")
            .order_by("document_id", "version_number", "id")
        )

        grouped: dict[int, list[DocumentVersion]] = {}
        for version in versions:
            grouped.setdefault(version.document_id, []).append(version)

        found = 0

        for document_id, items in grouped.items():
            for index in range(len(items) - 1):
                version_from = items[index]
                version_to = items[index + 1]

                diff_payload = build_version_diff(
                    from_version=version_from,
                    to_version=version_to,
                )

                if diff_payload["identical"]:
                    continue

                found += 1
                summary = diff_payload["summary"]
                self.stdout.write(
                    self.style.SUCCESS(
                        f"document_id={document_id} "
                        f"from_version_id={version_from.id} "
                        f"to_version_id={version_to.id} "
                        f"from_version_number={version_from.version_number} "
                        f"to_version_number={version_to.version_number} "
                        f"added={summary['added']} "
                        f"removed={summary['removed']} "
                        f"modified={summary['modified']} "
                        f"moved={summary['moved']} "
                        f"unchanged={summary['unchanged']}"
                    )
                )

        if found == 0:
            self.stdout.write(self.style.WARNING("No changed version pairs found."))
