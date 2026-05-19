from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET
from zipfile import BadZipFile

from docx import Document as DocxDocument
from docx.document import Document as DocxDocumentType
from docx.opc.exceptions import PackageNotFoundError
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from .text_processing import PDF_PAGE_BREAK, materialize_document_text


class TextExtractionError(Exception):
    """Base exception for predictable extraction failures."""


class UnsupportedFileTypeError(TextExtractionError):
    """Raised when the uploaded file format is not supported."""


class EmptyExtractedTextError(TextExtractionError):
    """Raised when a supported file contains no extractable text."""


class InvalidDocumentFileError(TextExtractionError):
    """Raised when a file has a supported extension but invalid binary content."""


@dataclass(frozen=True)
class ProcessedDocumentText:
    extracted_text: str
    normalized_text: str
    content_hash: str
    extension: str


TXT_ENCODINGS = ("utf-8-sig", "utf-8", "cp1251", "cp866")


def _detect_extension(filename: str) -> str:
    return Path(filename or "").suffix.lower()


def _iter_block_items(parent: DocxDocumentType | _Cell) -> Iterable[Paragraph | Table]:
    if isinstance(parent, DocxDocumentType):
        parent_element = parent.element.body
    else:
        parent_element = parent._tc

    for child in parent_element.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)


def _extract_table_text(table: Table) -> list[str]:
    rows_text: list[str] = []

    for row in table.rows:
        cells_text: list[str] = []
        for cell in row.cells:
            nested_parts: list[str] = []
            for item in _iter_block_items(cell):
                if isinstance(item, Paragraph):
                    value = item.text.strip()
                    if value:
                        nested_parts.append(value)
                elif isinstance(item, Table):
                    nested_table_text = "\n".join(_extract_table_text(item)).strip()
                    if nested_table_text:
                        nested_parts.append(nested_table_text)

            cell_text = "\n".join(part for part in nested_parts if part).strip()
            if cell_text:
                cells_text.append(cell_text)

        if cells_text:
            rows_text.append(" | ".join(cells_text))

    return rows_text


def extract_text_from_txt_bytes(data: bytes) -> str:
    decoded_text: str | None = None

    for encoding in TXT_ENCODINGS:
        try:
            decoded_text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue

    if decoded_text is None:
        raise InvalidDocumentFileError(
            "TXT file has unsupported encoding and cannot be decoded."
        )

    return decoded_text.replace("\r\n", "\n").replace("\r", "\n")


def extract_text_from_docx_bytes(data: bytes) -> str:
    try:
        document = DocxDocument(BytesIO(data))
    except (BadZipFile, PackageNotFoundError, ValueError) as error:
        raise InvalidDocumentFileError(
            "DOCX file is invalid or corrupted and cannot be processed."
        ) from error
    except Exception as error:  # noqa: BLE001
        raise InvalidDocumentFileError(
            "DOCX file is invalid or corrupted and cannot be processed."
        ) from error

    parts: list[str] = []

    for item in _iter_block_items(document):
        if isinstance(item, Paragraph):
            value = item.text.strip()
            if value:
                parts.append(value)
        elif isinstance(item, Table):
            parts.extend(_extract_table_text(item))

    return "\n".join(parts).strip()


def extract_text_from_pdf_bytes(data: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(data))
        pages_text: list[str] = []

        for page in reader.pages:
            page_text = (page.extract_text() or "").strip()
            if page_text:
                pages_text.append(page_text)
    except (PdfReadError, ValueError) as error:
        raise InvalidDocumentFileError(
            "PDF file is invalid or corrupted and cannot be processed."
        ) from error
    except Exception as error:  # noqa: BLE001
        raise InvalidDocumentFileError(
            "PDF file is invalid or corrupted and cannot be processed."
        ) from error

    return PDF_PAGE_BREAK.join(pages_text).strip()


def extract_text_from_xml_bytes(data: bytes) -> str:
    try:
        decoded = extract_text_from_txt_bytes(data)
        root = ET.fromstring(decoded)
    except ET.ParseError as error:
        raise InvalidDocumentFileError(
            "XML file is invalid or corrupted and cannot be processed."
        ) from error
    except InvalidDocumentFileError:
        raise
    except Exception as error:  # noqa: BLE001
        raise InvalidDocumentFileError(
            "XML file is invalid or corrupted and cannot be processed."
        ) from error

    return "\n".join(part.strip() for part in root.itertext() if part.strip()).strip()


def extract_text_from_bytes(data: bytes, filename: str) -> str:
    extension = _detect_extension(filename)

    if extension == ".txt":
        return extract_text_from_txt_bytes(data)
    if extension == ".docx":
        return extract_text_from_docx_bytes(data)
    if extension == ".pdf":
        return extract_text_from_pdf_bytes(data)
    if extension == ".xml":
        return extract_text_from_xml_bytes(data)

    raise UnsupportedFileTypeError(
        f"Unsupported file extension: {extension or 'unknown'}"
    )


def process_uploaded_file(
    uploaded_file, source_filename: str | None = None
) -> ProcessedDocumentText:
    filename = source_filename or getattr(uploaded_file, "name", "") or ""
    extension = _detect_extension(filename)

    uploaded_file.seek(0)
    data = uploaded_file.read()
    uploaded_file.seek(0)

    extracted_text = extract_text_from_bytes(data=data, filename=filename).strip()
    materialized = materialize_document_text(extracted_text, extension=extension)

    if not materialized.normalized_text:
        if extension == ".pdf":
            raise EmptyExtractedTextError(
                "PDF does not contain extractable text. OCR is not supported in Phase 5."
            )
        raise EmptyExtractedTextError(
            "Uploaded file does not contain extractable text."
        )

    return ProcessedDocumentText(
        extracted_text=extracted_text,
        normalized_text=materialized.normalized_text,
        content_hash=materialized.content_hash,
        extension=extension,
    )
