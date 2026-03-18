from __future__ import annotations

import logging

from django.conf import settings

from .models import Chunk, DocumentVersion
from .qdrant_service import index_chunks
from .text_processing import chunk_by_structure_ru, normalize_text, sha256_hex

logger = logging.getLogger("documents.ingestion")


def rebuild_version_chunks(version: DocumentVersion, *, reindex: bool = True) -> int:
    """Normalize extracted text, rebuild chunks, and optionally reindex them."""
    normalized = normalize_text(version.extracted_text or "")
    version.normalized_text = normalized
    version.content_hash = sha256_hex(normalized)
    version.save(update_fields=["normalized_text", "content_hash"])

    version.chunks.all().delete()

    chunk_specs = chunk_by_structure_ru(normalized)
    if not chunk_specs:
        return 0

    Chunk.objects.bulk_create(
        [
            Chunk(
                version=version,
                chunk_index=chunk.chunk_index,
                heading=chunk.heading,
                section_path=chunk.section_path,
                text=chunk.text,
                text_hash=chunk.text_hash,
            )
            for chunk in chunk_specs
        ]
    )

    if reindex:
        safe_index_version_chunks(version)

    return len(chunk_specs)


def safe_index_version_chunks(version: DocumentVersion) -> int:
    if not settings.QDRANT_ENABLED:
        return 0

    try:
        return index_chunks(version.id)
    except Exception as error:  # noqa: BLE001
        logger.warning(
            "Chunk indexing skipped for version_id=%s: %s",
            version.id,
            error,
        )
        return 0
