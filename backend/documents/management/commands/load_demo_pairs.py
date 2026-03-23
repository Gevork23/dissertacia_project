from __future__ import annotations

import logging

from django.core.management.base import BaseCommand

from documents.demo.corpus import DEMO_DOCUMENTS, DemoDocumentSpec, DemoVersionSpec
from documents.models import Document, DocumentVersion
from documents.services.search import index_chunks
from documents.services.versioning import create_text_document_version

logger = logging.getLogger(__name__)


def safe_index_chunks(version_id: int) -> None:
    try:
        index_chunks(version_id)
    except Exception as error:  # noqa: BLE001
        logger.warning(
            "Demo indexing skipped for version_id=%s: %s",
            version_id,
            error,
        )


class Command(BaseCommand):
    help = (
        "Load deterministic MFC/NPA demo corpus for compare/brief/quiz "
        "and future AI-analysis scenarios."
    )

    def handle(self, *args, **options):
        self.stdout.write("Removing old demo corpus documents...")

        demo_titles = [spec.title for spec in DEMO_DOCUMENTS]
        old_documents = Document.objects.filter(title__in=demo_titles)
        old_count = old_documents.count()
        old_documents.delete()

        self.stdout.write(f"Deleted old demo documents: {old_count}")
        self.stdout.write("")

        all_pairs: list[dict[str, object]] = []

        for document_spec in DEMO_DOCUMENTS:
            pair_info = self._create_demo_document(document_spec)
            all_pairs.append(pair_info)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Demo corpus is ready."))
        self.stdout.write("")

        self.stdout.write(self.style.SUCCESS("Available demo pairs:"))
        for pair in all_pairs:
            self.stdout.write(
                f"- {pair['scenario']}: "
                f"from_version={pair['from_version_id']} "
                f"to_version={pair['to_version_id']} "
                f'| document="{pair["title"]}"'
            )

        self.stdout.write("")
        self.stdout.write("Suggested URLs for manual проверки:")
        for pair in all_pairs:
            from_version_id = pair["from_version_id"]
            to_version_id = pair["to_version_id"]
            self.stdout.write(
                f"/api/compare/?from_version={from_version_id}"
                f"&to_version={to_version_id}"
            )
            self.stdout.write(
                f"/api/compare/brief/?from_version={from_version_id}"
                f"&to_version={to_version_id}"
            )
            self.stdout.write(
                f"/api/compare/quiz/?from_version={from_version_id}"
                f"&to_version={to_version_id}"
            )
            self.stdout.write("")

        self.stdout.write("Example save-quiz curl:")
        first_pair = all_pairs[0]
        self.stdout.write(
            'curl -X POST "http://localhost:8000/api/compare/quiz/save/" '
            '\\
  -H "Content-Type: application/json" '
            f'\\
  -d \'{{"from_version":{first_pair["from_version_id"]},'
            f'"to_version":{first_pair["to_version_id"]},'
            '"title":"Demo quiz","limit":10}\''
        )

    def _create_demo_document(
        self,
        document_spec: DemoDocumentSpec,
    ) -> dict[str, object]:
        self.stdout.write(
            self.style.SUCCESS(
                f'Creating document: "{document_spec.title}" '
                f"[{document_spec.scenario}]"
            )
        )

        document = Document.objects.create(
            title=document_spec.title,
            description=document_spec.description,
        )

        created_versions: list[DocumentVersion] = []

        for version_spec in document_spec.versions:
            version = self._create_version(
                document=document,
                version_spec=version_spec,
            )
            created_versions.append(version)

            self.stdout.write(
                f"  version={version.version_number} "
                f"id={version.id} "
                f"chunks={version.chunks.count()}"
            )

        first_version = created_versions[0]
        second_version = created_versions[1]

        return {
            "slug": document_spec.slug,
            "title": document_spec.title,
            "scenario": document_spec.scenario,
            "from_version_id": first_version.id,
            "to_version_id": second_version.id,
        }

    def _create_version(
        self,
        document: Document,
        version_spec: DemoVersionSpec,
    ) -> DocumentVersion:
        version = create_text_document_version(
            document=document,
            source_filename=version_spec.source_filename,
            raw_text=version_spec.text.strip(),
            version_number=version_spec.version_number,
            allow_duplicate_content=True,
        )
        safe_index_chunks(version.id)
        return version
