from __future__ import annotations

from collections import Counter

from django.core.management.base import BaseCommand, CommandError

from documents.analysis_service import analyze_version_entities
from documents.entity_schema import ExtractionMethod
from documents.models import ChunkAnalysis, DocumentVersion


def _entity_key(entity: dict) -> tuple[str, str, str]:
    return (
        str(entity.get("entity_type", "")),
        str(entity.get("normalized_value", "")),
        str(entity.get("value", "")),
    )


def _collect_entities(version: DocumentVersion, method: str) -> list[dict]:
    analyses = ChunkAnalysis.objects.filter(
        chunk__version=version,
        extraction_method=method,
    ).order_by("chunk__chunk_index")

    entities: list[dict] = []
    for analysis in analyses:
        entities.extend(analysis.entities)
    return entities


def _count_types(entities: list[dict]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for entity in entities:
        counter[str(entity.get("entity_type", "unknown"))] += 1
    return dict(sorted(counter.items()))


class Command(BaseCommand):
    help = "Compare rules / llm / hybrid extraction across demo corpus versions."

    def add_arguments(self, parser):
        parser.add_argument(
            "--document-id",
            type=int,
            help="Optional document id filter.",
        )
        parser.add_argument(
            "--run-missing",
            action="store_true",
            help="Run missing analyses automatically.",
        )

    def handle(self, *args, **options):
        document_id = options.get("document_id")
        run_missing = options.get("run_missing", False)

        queryset = DocumentVersion.objects.filter(
            document__title__startswith="DEMO МФЦ:"
        ).order_by("document_id", "version_number", "id")

        if document_id:
            queryset = queryset.filter(document_id=document_id)

        versions = list(queryset)
        if not versions:
            raise CommandError("Demo versions were not found.")

        methods = [
            ExtractionMethod.RULE_BASED.value,
            ExtractionMethod.LLM.value,
            ExtractionMethod.HYBRID.value,
        ]

        if run_missing:
            for version in versions:
                for mode in ("rules", "llm", "hybrid"):
                    analyze_version_entities(version, mode=mode)

        totals = {
            method: {
                "versions": 0,
                "entities": 0,
                "types": Counter(),
            }
            for method in methods
        }

        overlaps = {
            "rules_vs_llm": 0,
            "rules_vs_hybrid": 0,
            "llm_vs_hybrid": 0,
            "rules_total": 0,
            "llm_total": 0,
            "hybrid_total": 0,
        }

        for version in versions:
            aggregated = {
                method: _collect_entities(version, method) for method in methods
            }

            missing = [method for method, items in aggregated.items() if not items]
            if missing:
                raise CommandError(
                    f"Missing analyses for version_id={version.id}: {missing}. "
                    "Run analyze_entities first or use --run-missing."
                )

            self.stdout.write(
                self.style.SUCCESS(
                    f"version_id={version.id} "
                    f"document_id={version.document_id} "
                    f"version_number={version.version_number} "
                    f'document="{version.document.title}"'
                )
            )

            for method in methods:
                entities = aggregated[method]
                totals[method]["versions"] += 1
                totals[method]["entities"] += len(entities)
                totals[method]["types"].update(_count_types(entities))

                self.stdout.write(
                    f"  {method}: count={len(entities)} "
                    f"by_type={_count_types(entities)}"
                )

            rules_set = {
                _entity_key(item)
                for item in aggregated[ExtractionMethod.RULE_BASED.value]
            }
            llm_set = {
                _entity_key(item) for item in aggregated[ExtractionMethod.LLM.value]
            }
            hybrid_set = {
                _entity_key(item) for item in aggregated[ExtractionMethod.HYBRID.value]
            }

            overlaps["rules_vs_llm"] += len(rules_set & llm_set)
            overlaps["rules_vs_hybrid"] += len(rules_set & hybrid_set)
            overlaps["llm_vs_hybrid"] += len(llm_set & hybrid_set)
            overlaps["rules_total"] += len(rules_set)
            overlaps["llm_total"] += len(llm_set)
            overlaps["hybrid_total"] += len(hybrid_set)

            self.stdout.write("")

        self.stdout.write(self.style.SUCCESS("TOTALS"))
        for method in methods:
            self.stdout.write(
                f"{method}: "
                f'versions={totals[method]["versions"]} '
                f'entities={totals[method]["entities"]} '
                f'by_type={dict(sorted(totals[method]["types"].items()))}'
            )

        self.stdout.write("")
        self.stdout.write(
            "overlap: "
            f'rules_vs_llm={overlaps["rules_vs_llm"]}/'
            f'{overlaps["rules_total"]} '
            f'rules_vs_hybrid={overlaps["rules_vs_hybrid"]}/'
            f'{overlaps["rules_total"]} '
            f'llm_vs_hybrid={overlaps["llm_vs_hybrid"]}/'
            f'{overlaps["llm_total"]}'
        )
