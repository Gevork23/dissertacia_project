from __future__ import annotations

from collections import Counter

from django.core.management.base import BaseCommand, CommandError
from documents.domain.entity_schema import ExtractionMethod
from documents.models import ChunkAnalysis, DocumentVersion
from documents.services.analysis import analyze_version_entities


def _count_entity_types(entities: list[dict]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for entity in entities:
        counter[str(entity.get("entity_type", "unknown"))] += 1
    return dict(sorted(counter.items()))


def _entity_key(entity: dict) -> tuple[str, str, str]:
    return (
        str(entity.get("entity_type", "")),
        str(entity.get("normalized_value", "")),
        str(entity.get("value", "")),
    )


class Command(BaseCommand):
    help = (
        "Compare entity extraction results across rules / llm / hybrid "
        "for one document version."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--version-id",
            type=int,
            required=True,
            help="DocumentVersion id to compare.",
        )
        parser.add_argument(
            "--run-missing",
            action="store_true",
            help="Run missing analyses automatically before comparison.",
        )

    def handle(self, *args, **options):
        version_id = options["version_id"]
        run_missing = options["run_missing"]

        try:
            version = DocumentVersion.objects.get(pk=version_id)
        except DocumentVersion.DoesNotExist as error:
            raise CommandError(
                f"DocumentVersion with id={version_id} was not found."
            ) from error

        methods = [
            ExtractionMethod.RULE_BASED.value,
            ExtractionMethod.LLM.value,
            ExtractionMethod.HYBRID.value,
        ]

        if run_missing:
            for mode in ("rules", "llm", "hybrid"):
                analyze_version_entities(version, mode=mode)

        analyses = {
            method: list(
                ChunkAnalysis.objects.filter(
                    chunk__version=version,
                    extraction_method=method,
                ).order_by("chunk__chunk_index")
            )
            for method in methods
        }

        for method in methods:
            if not analyses[method]:
                raise CommandError(
                    f"No analyses found for version_id={version_id}, method={method}. "
                    "Run analyze_entities first or use --run-missing."
                )

        aggregated: dict[str, list[dict]] = {}
        for method, items in analyses.items():
            entities: list[dict] = []
            for analysis in items:
                entities.extend(analysis.entities)
            aggregated[method] = entities

        rules_set = {
            _entity_key(item) for item in aggregated[ExtractionMethod.RULE_BASED.value]
        }
        llm_set = {_entity_key(item) for item in aggregated[ExtractionMethod.LLM.value]}
        hybrid_set = {
            _entity_key(item) for item in aggregated[ExtractionMethod.HYBRID.value]
        }

        rules_llm_overlap = len(rules_set & llm_set)
        rules_hybrid_overlap = len(rules_set & hybrid_set)
        llm_hybrid_overlap = len(llm_set & hybrid_set)

        self.stdout.write(
            self.style.SUCCESS(
                f"version_id={version.id} document_id={version.document_id} "
                f'document="{version.document.title}"'
            )
        )
        self.stdout.write("")

        for method in methods:
            entities = aggregated[method]
            counts = _count_entity_types(entities)
            self.stdout.write(f"{method}: entities={len(entities)} by_type={counts}")

        self.stdout.write("")
        self.stdout.write(
            f"rules_vs_llm_overlap={rules_llm_overlap} "
            f"rules_total={len(rules_set)} llm_total={len(llm_set)}"
        )
        self.stdout.write(
            f"rules_vs_hybrid_overlap={rules_hybrid_overlap} "
            f"hybrid_total={len(hybrid_set)}"
        )
        self.stdout.write(f"llm_vs_hybrid_overlap={llm_hybrid_overlap}")
