from __future__ import annotations

from .ingestion import (
    DuplicateDocumentVersionError,
    InvalidDocumentVersionFileError,
    ingest_text_document_version,
    ingest_uploaded_document_version,
    sanitize_source_filename,
    validate_uploaded_version_file,
)

__all__ = [
    "DuplicateDocumentVersionError",
    "InvalidDocumentVersionFileError",
    "sanitize_source_filename",
    "validate_uploaded_version_file",
    "create_uploaded_document_version",
    "create_text_document_version",
]


def create_uploaded_document_version(
    *,
    document,
    uploaded_file,
    source_filename: str = "",
    source_revision_id: str = "",
    effective_date=None,
):
    return ingest_uploaded_document_version(
        document=document,
        uploaded_file=uploaded_file,
        source_filename=source_filename,
        source_revision_id=source_revision_id,
        effective_date=effective_date,
    )


def create_text_document_version(
    *,
    document,
    source_filename: str,
    raw_text: str,
    version_number: int | None = None,
    source_revision_id: str = "",
    effective_date=None,
    allow_duplicate_content: bool = False,
):
    return ingest_text_document_version(
        document=document,
        source_filename=source_filename,
        raw_text=raw_text,
        version_number=version_number,
        source_revision_id=source_revision_id,
        effective_date=effective_date,
        allow_duplicate_content=allow_duplicate_content,
    )
