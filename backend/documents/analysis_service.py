from __future__ import annotations

from django.db import transaction

from .entity_extraction import extract_entities_from_text
from .entity_schema import ExtractionMethod
from .llm_entity_extraction import get_default_llm_entity_extractor
from .models import Chunk, ChunkAnalysis, DocumentVersion


def normalize_analysis_mode(mode: str) -> str:
    lowered = (mode or "").strip().lower()

    if lowered in {"rules", "rule", "rule_based"}:
        return ExtractionMethod.RULE_BASED.value
    if lowered == "llm":
        return ExtractionMethod.LLM.value
    if lowered == "hybrid":
        return ExtractionMethod.HYBRID.value

    raise ValueError(f"Unsupported analysis mode: {mode}")


def _entity_identity(entity: dict) -> tuple[str, str, str]:
    return (
        str(entity.get("entity_type", "")),
        str(entity.get("normalized_value", "")),
        str(entity.get("value", "")),
    )


def merge_rule_and_llm_entities(
    rule_entities: list[dict],
    llm_entities: list[dict],
) -> list[dict]:
    merged: dict[tuple[str, str, str], dict] = {}

    for entity in rule_entities:
        hybrid_entity = dict(entity)
        hybrid_entity["extraction_method"] = ExtractionMethod.HYBRID.value
        merged[_entity_identity(hybrid_entity)] = hybrid_entity

    for entity in llm_entities:
        hybrid_entity = dict(entity)
        hybrid_entity["extraction_method"] = ExtractionMethod.HYBRID.value
        key = _entity_identity(hybrid_entity)

        existing = merged.get(key)
        if existing is None:
            merged[key] = hybrid_entity
            continue

        if float(hybrid_entity.get("confidence", 0)) >= float(
            existing.get("confidence", 0)
        ):
            merged[key] = hybrid_entity

    return sorted(
        merged.values(),
        key=lambda item: (
            int(item.get("start_char", 0)),
            str(item.get("entity_type", "")),
            str(item.get("value", "")),
        ),
    )


def extract_entities_by_mode(
    text: str,
    *,
    heading: str = "",
    section_path: str = "",
    mode: str = "rules",
    llm_extractor=None,
) -> list[dict]:
    normalized_mode = normalize_analysis_mode(mode)

    if normalized_mode == ExtractionMethod.RULE_BASED.value:
        return extract_entities_from_text(
            text,
            heading=heading,
            section_path=section_path,
        )

    if llm_extractor is None:
        llm_extractor = get_default_llm_entity_extractor()

    if normalized_mode == ExtractionMethod.LLM.value:
        return llm_extractor.extract(
            text,
            heading=heading,
            section_path=section_path,
        )

    rule_entities = extract_entities_from_text(
        text,
        heading=heading,
        section_path=section_path,
    )
    llm_entities = llm_extractor.extract(
        text,
        heading=heading,
        section_path=section_path,
    )
    return merge_rule_and_llm_entities(rule_entities, llm_entities)


def analyze_chunk_entities(
    chunk: Chunk,
    mode: str = "rules",
    llm_extractor=None,
) -> ChunkAnalysis:
    extraction_method = normalize_analysis_mode(mode)
    entities = extract_entities_by_mode(
        chunk.text,
        heading=chunk.heading,
        section_path=chunk.section_path,
        mode=mode,
        llm_extractor=llm_extractor,
    )

    analysis, _created = ChunkAnalysis.objects.update_or_create(
        chunk=chunk,
        extraction_method=extraction_method,
        defaults={
            "entities": entities,
            "entities_count": len(entities),
        },
    )
    return analysis


@transaction.atomic
def analyze_version_entities(
    version: DocumentVersion,
    mode: str = "rules",
    llm_extractor=None,
) -> dict[str, object]:
    extraction_method = normalize_analysis_mode(mode)
    analyses: list[ChunkAnalysis] = []
    total_entities = 0

    chunks = version.chunks.all().order_by("chunk_index")

    for chunk in chunks:
        analysis = analyze_chunk_entities(
            chunk=chunk,
            mode=mode,
            llm_extractor=llm_extractor,
        )
        analyses.append(analysis)
        total_entities += analysis.entities_count

    return {
        "version_id": version.id,
        "document_id": version.document_id,
        "chunks_count": len(analyses),
        "entities_count": total_entities,
        "analysis_ids": [analysis.id for analysis in analyses],
        "extraction_method": extraction_method,
    }