from __future__ import annotations

from pathlib import Path
from typing import Callable

from docx import Document as DocxDocument


def extract_text_from_txt(file_path: str) -> str:
    # пробуем utf-8, если не вышло — cp1251 (часто для ру-текстов)
    p = Path(file_path)
    try:
        return p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return p.read_text(encoding="cp1251", errors="replace")


def extract_text_from_docx(file_path: str) -> str:
    doc = DocxDocument(file_path)
    parts: list[str] = []
    for para in doc.paragraphs:
        text = (para.text or "").strip()
        if text:
            parts.append(text)
    return "\n".join(parts)


def extract_text_by_extension(file_path: str) -> str:
    ext = Path(file_path).suffix.lower()
    if ext == ".txt":
        return extract_text_from_txt(file_path)
    if ext == ".docx":
        return extract_text_from_docx(file_path)
    # пока только TXT/DOCX для MVP
    return ""
