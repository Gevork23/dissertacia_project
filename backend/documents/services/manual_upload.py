from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from django.http import HttpRequest

from ..domain.text_extractors import process_uploaded_file


@dataclass(frozen=True)
class ManualUploadExtractionResult:
    text: str
    warning: str


def extract_text_from_uploaded_file(uploaded_file) -> ManualUploadExtractionResult:
    filename = getattr(uploaded_file, "name", "") or ""
    try:
        processed = process_uploaded_file(uploaded_file, source_filename=filename)
    except Exception as error:  # noqa: BLE001
        extension = Path(filename).suffix.lower() or "unknown"
        return ManualUploadExtractionResult(
            text="",
            warning=f"Не удалось извлечь текст из файла {extension}: {error}",
        )
    return ManualUploadExtractionResult(text=processed.extracted_text, warning="")


def _serialize_rag_chunks(version) -> list[dict[str, object]]:
    version_label = f"v{version.version_number}"
    return [
        {
            "chunk_id": f"{version.id}:{chunk.id or chunk.chunk_index}",
            "document_id": version.document_id,
            "document_title": version.document.title,
            "version_id": version.id,
            "version_number": version.version_number,
            "version_label": version_label,
            "heading": chunk.heading,
            "section_path": chunk.section_path,
            "text": chunk.text,
            "fragment_type": chunk.fragment_type,
            "chunk_index": chunk.chunk_index,
        }
        for chunk in version.chunks.order_by("chunk_index")
    ]


def refresh_manual_rag_chunks(request: HttpRequest, *, document) -> None:
    versions = list(
        document.versions.order_by("-version_number").prefetch_related("chunks")[:2]
    )
    versions.reverse()
    request.session["rag_chunks"] = [
        chunk
        for version in versions
        for chunk in _serialize_rag_chunks(version)
    ]
    request.session.modified = True
