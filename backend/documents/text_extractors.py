# backend/documents/text_extractors.py
from __future__ import annotations

from pathlib import Path

from docx import Document as DocxDocument


def extract_text_from_txt(path: str) -> str:
    return Path(path).read_text(encoding="utf-8", errors="ignore")


def extract_text_from_docx(path: str) -> str:
    doc = DocxDocument(path)
    parts = [p.text for p in doc.paragraphs if p.text and p.text.strip()]
    return "\n".join(parts).strip()


def extract_text_by_extension(path: str) -> str:
    p = Path(path)
    ext = p.suffix.lower()

    if ext == ".txt":
        return extract_text_from_txt(str(p))
    if ext == ".docx":
        return extract_text_from_docx(str(p))

    raise ValueError(f"Unsupported file extension: {ext}")
