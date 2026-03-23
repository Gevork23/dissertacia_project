from __future__ import annotations

import mimetypes
from pathlib import Path

from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from ..domain.text_extractors import (
    EmptyExtractedTextError,
    TextExtractionError,
    process_uploaded_file,
)
from ..domain.text_processing import normalize_text, sha256_hex
from ..models import ALLOWED_DOCUMENT_EXTENSIONS, Document, DocumentVersion
from .ingestion import rebuild_version_chunks


class DuplicateDocumentVersionError(ValueError):
    """Raised when the same document content is uploaded more than once."""


class InvalidDocumentVersionFileError(ValueError):
    """Raised when the provided file cannot be accepted as a document version."""


def sanitize_source_filename(value: str) -> str:
    return Path((value or "").strip()).name


def validate_uploaded_version_file(uploaded_file) -> None:
    extension = Path(uploaded_file.name).suffix.lower()
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


@transaction.atomic
def create_uploaded_document_version(
    *,
    document: Document,
    uploaded_file,
    source_filename: str = "",
    source_revision_id: str = "",
    effective_date=None,
) -> DocumentVersion:
    validate_uploaded_version_file(uploaded_file)

    source_filename = sanitize_source_filename(source_filename) or uploaded_file.name
    content_type = (
        getattr(uploaded_file, "content_type", "")
        or mimetypes.guess_type(source_filename)[0]
        or ""
    )
    file_size = getattr(uploaded_file, "size", 0) or 0

    try:
        processed_text = process_uploaded_file(
            uploaded_file=uploaded_file,
            source_filename=source_filename,
        )
    except (EmptyExtractedTextError, TextExtractionError):
        raise

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
def create_text_document_version(
    *,
    document: Document,
    source_filename: str,
    raw_text: str,
    version_number: int | None = None,
    source_revision_id: str = "",
    effective_date=None,
    allow_duplicate_content: bool = False,
) -> DocumentVersion:
    normalized = normalize_text(raw_text or "")
    content_hash = sha256_hex(normalized)
    locked_document = Document.objects.select_for_update().get(pk=document.pk)
    if not allow_duplicate_content:
        _assert_unique_content_hash(document=locked_document, content_hash=content_hash)

    assigned_version_number = version_number or _next_version_number(locked_document)
    content = ContentFile((raw_text or "").encode("utf-8"))
    content.name = sanitize_source_filename(source_filename) or "document.txt"

    version = DocumentVersion(
        document=locked_document,
        version_number=assigned_version_number,
        source_filename=content.name,
        source_revision_id=(source_revision_id or "").strip(),
        effective_date=effective_date,
        file_size=content.size,
        content_type=mimetypes.guess_type(content.name)[0] or "text/plain",
        extracted_text=raw_text or "",
        normalized_text=normalized,
        content_hash=content_hash,
    )
    version.file.save(content.name, content, save=False)
    version.save()
    rebuild_version_chunks(version)
    _touch_document(locked_document, version)
    return version
