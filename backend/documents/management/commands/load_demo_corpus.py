from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from documents.demo.file_corpus import (
    DEMO_DOCUMENT_TITLE_PREFIX,
    DemoCorpusError,
    DemoDocumentSpec,
    DemoVersionSpec,
    get_default_demo_corpus_dir,
    load_demo_document_specs,
)
from documents.models import Document, DocumentVersion
from documents.services.versioning import create_text_document_version


class Command(BaseCommand):
    help = "Load the file-backed Phase 12 demo corpus into local demo documents."

    def add_arguments(self, parser):
        parser.add_argument(
            "--corpus-dir",
            default="",
            help="Path to demo corpus directory. Defaults to data/demo_corpus.",
        )
        parser.add_argument(
            "--keep-existing",
            action="store_true",
            help=(
                "Do not remove existing demo documents before loading. "
                "By default, documents with the DEMO prefix are replaced."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate and list corpus pairs without writing to the database.",
        )

    def handle(self, *args, **options):
        corpus_dir = Path(options["corpus_dir"] or get_default_demo_corpus_dir())

        try:
            document_specs = load_demo_document_specs(corpus_dir)
        except DemoCorpusError as error:
            raise CommandError(str(error)) from error

        self.stdout.write(f"Demo corpus directory: {corpus_dir}")
        self.stdout.write(f"Pairs found: {len(document_specs)}")

        if options["dry_run"]:
            for spec in document_specs:
                self.stdout.write(f"- {spec.pair_id}: {spec.title} [{spec.scenario}]")
            self.stdout.write(self.style.SUCCESS("Demo corpus dry-run passed."))
            return

        if not options["keep_existing"]:
            old_documents = Document.objects.filter(
                title__startswith=DEMO_DOCUMENT_TITLE_PREFIX
            )
            old_count = old_documents.count()
            old_documents.delete()
            self.stdout.write(f"Deleted old demo documents: {old_count}")

        all_pairs: list[dict[str, object]] = []
        for document_spec in document_specs:
            all_pairs.append(self._create_demo_document(document_spec))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Demo corpus is ready."))
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Available demo pairs:"))
        for pair in all_pairs:
            self.stdout.write(
                f"- {pair['pair_id']} | {pair['scenario']}: "
                f"from_version={pair['from_version_id']} "
                f"to_version={pair['to_version_id']} "
                f"| document=\"{pair['title']}\""
            )

        self.stdout.write("")
        self.stdout.write("Suggested URLs for manual checks:")
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

        if all_pairs:
            first_pair = all_pairs[0]
            payload = (
                f'{{"from_version":{first_pair["from_version_id"]},'
                f'"to_version":{first_pair["to_version_id"]},'
                '"title":"Demo quiz","limit":10}'
            )
            self.stdout.write("Example save-quiz curl:")
            self.stdout.write(
                'curl -X POST "http://localhost:8000/api/compare/quiz/save/" '
                '-H "Content-Type: application/json" '
                f"-d '{payload}'"
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
            "pair_id": document_spec.pair_id,
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
        return create_text_document_version(
            document=document,
            source_filename=version_spec.source_filename,
            raw_text=version_spec.text,
            version_number=version_spec.version_number,
            allow_duplicate_content=True,
        )
