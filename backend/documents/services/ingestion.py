from __future__ import annotations

import logging
import mimetypes
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from ..domain.text_extractors import process_uploaded_file
from ..domain.text_processing import chunk_by_structure_ru, normalize_text, sha256_hex
from ..models import ALLOWED_DOCUMENT_EXTENSIONS, Chunk, Document, DocumentVersion
from .search import index_chunks

logger = logging.getLogger("documents.ingestion")


class DuplicateDocumentVersionError(ValueError):
    """Raised when the same document content is uploaded more than once."""


class InvalidDocumentVersionFileError(ValueError):
    """Raised when the provided file cannot be accepted as a document version."""


def sanitize_source_filename(value: str) -> str:
    return Path((value or "").strip()).name


def validate_uploaded_version_file(uploaded_file) -> None:
    filename = getattr(uploaded_file, "name", "") or ""
    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_DOCUMENT_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_DOCUMENT_EXTENSIONS))
        raise InvalidDocumentVersionFileError(
            f"Unsupported file type. Allowed extensions: {allowed}."
        )

    if getattr(uploaded_file, "size", 0) <= 0:
        raise InvalidDocumentVersionFileError("Uploaded file is empty.")


def _next_version_number(document: Document) -> int:
    current_max = (
        document.versions.aggregate(max_number=Max("version_number"))["max_number"] or 0
    )
    return current_max + 1


def _assert_unique_content_hash(*, document: Document, content_hash: str) -> None:
    if not content_hash:
        return

    if document.versions.filter(content_hash=content_hash).exists():
        raise DuplicateDocumentVersionError(
            "A version with the same normalized content already exists for this document."
        )


def _touch_document(document: Document, version: DocumentVersion) -> None:
    Document.objects.filter(pk=document.pk).update(
        current_version=version,
        updated_at=timezone.now(),
    )
    document.current_version = version
    document.updated_at = timezone.now()


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


@transaction.atomic
def ingest_uploaded_document_version(
    *,
    document: Document,
    uploaded_file,
    source_filename: str = "",
    source_revision_id: str = "",
    effective_date=None,
) -> DocumentVersion:
    validate_uploaded_version_file(uploaded_file)

    source_filename = sanitize_source_filename(
        source_filename
    ) or sanitize_source_filename(getattr(uploaded_file, "name", ""))
    content_type = (
        getattr(uploaded_file, "content_type", "")
        or mimetypes.guess_type(source_filename)[0]
        or ""
    )
    file_size = getattr(uploaded_file, "size", 0) or 0

    processed_text = process_uploaded_file(
        uploaded_file=uploaded_file,
        source_filename=source_filename,
    )

    locked_document = Document.objects.select_for_update().get(pk=document.pk)
    _assert_unique_content_hash(
        document=locked_document,
        content_hash=processed_text.content_hash,
    )

    version = DocumentVersion.objects.create(
        document=locked_document,
        version_number=_next_version_number(locked_document),
        source_filename=source_filename,
        source_revision_id=(source_revision_id or "").strip(),
        effective_date=effective_date,
        file=uploaded_file,
        file_size=file_size,
        content_type=content_type,
        extracted_text=processed_text.extracted_text,
        normalized_text=processed_text.normalized_text,
        content_hash=processed_text.content_hash,
    )
    rebuild_version_chunks(version)
    _touch_document(locked_document, version)
    return version


@transaction.atomic
def ingest_text_document_version(
    *,
    document: Document,
    source_filename: str,
    raw_text: str,
    version_number: int | None = None,
    source_revision_id: str = "",
    effective_date=None,
    allow_duplicate_content: bool = False,
) -> DocumentVersion:
    extracted_text = raw_text or ""
    normalized_text = normalize_text(extracted_text)

    if not normalized_text:
        raise InvalidDocumentVersionFileError(
            "Document text is empty after normalization and cannot be materialized as a version."
        )

    content_hash = sha256_hex(normalized_text)
    locked_document = Document.objects.select_for_update().get(pk=document.pk)

    if not allow_duplicate_content:
        _assert_unique_content_hash(
            document=locked_document,
            content_hash=content_hash,
        )

    assigned_version_number = version_number or _next_version_number(locked_document)

    content = ContentFile(extracted_text.encode("utf-8"))
    content.name = sanitize_source_filename(source_filename) or "document.txt"

    version = DocumentVersion(
        document=locked_document,
        version_number=assigned_version_number,
        source_filename=content.name,
        source_revision_id=(source_revision_id or "").strip(),
        effective_date=effective_date,
        file_size=content.size,
        content_type=mimetypes.guess_type(content.name)[0] or "text/plain",
        extracted_text=extracted_text,
        normalized_text=normalized_text,
        content_hash=content_hash,
    )
    version.file.save(content.name, content, save=False)
    version.save()
    rebuild_version_chunks(version)
    _touch_document(locked_document, version)
    return version
