from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

MAX_CHUNK_LEN = 2200
SOFT_CHUNK_LEN = 1400


def normalize_text(text: str) -> str:
    if not text:
        return ""

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("—", "-").replace("–", "-")
    text = text.replace("\xa0", " ")

    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ChunkData:
    chunk_index: int
    heading: str
    section_path: str
    text: str
    text_hash: str


SECTION_RE = re.compile(
    r"^(?P<kind>РАЗДЕЛ|Раздел|ГЛАВА|Глава|СТАТЬЯ|Статья|ПУНКТ|Пункт)\s+"
    r"(?P<num>[0-9IVXLC]+(?:\.[0-9]+)*)\.?\s*(?P<title>.*)$"
)

LIST_ITEM_RE = re.compile(r"^\s*(?:\d+\)|\d+\.|-\s+|•\s+|[а-яА-Я]\))")


def normalize_heading_label(kind: str, num: str, title: str) -> str:
    kind_upper = kind.upper()
    kind_title = kind_upper.title()
    label = f"{kind_title} {num}".strip()
    title = title.strip()
    if title:
        label = f"{label}: {title}"
    return label


def split_large_block(text: str, max_len: int = MAX_CHUNK_LEN) -> list[str]:
    text = text.strip()
    if not text:
        return []

    if len(text) <= max_len:
        return [text]

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(paragraphs) <= 1:
        return split_by_lines(text=text, max_len=max_len)

    parts: list[str] = []
    buffer: list[str] = []
    current_len = 0

    for paragraph in paragraphs:
        extra_len = len(paragraph) + (2 if buffer else 0)

        if buffer and current_len + extra_len > max_len:
            parts.append("\n\n".join(buffer).strip())
            buffer = [paragraph]
            current_len = len(paragraph)
            continue

        buffer.append(paragraph)
        current_len += extra_len

    if buffer:
        parts.append("\n\n".join(buffer).strip())

    return parts


def split_by_lines(text: str, max_len: int = MAX_CHUNK_LEN) -> list[str]:
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if not lines:
        return []

    parts: list[str] = []
    buffer: list[str] = []
    current_len = 0

    for line in lines:
        extra_len = len(line) + (1 if buffer else 0)

        if buffer and current_len + extra_len > max_len:
            parts.append("\n".join(buffer).strip())
            buffer = [line]
            current_len = len(line)
            continue

        buffer.append(line)
        current_len += extra_len

    if buffer:
        parts.append("\n".join(buffer).strip())

    return parts


def append_chunk(
    chunks: list[ChunkData],
    heading: str,
    section_path: str,
    text: str,
) -> None:
    block = text.strip()
    if not block:
        return

    pieces = split_large_block(block)
    for piece in pieces:
        chunk_index = len(chunks) + 1
        chunks.append(
            ChunkData(
                chunk_index=chunk_index,
                heading=heading,
                section_path=section_path,
                text=piece,
                text_hash=sha256_hex(piece),
            )
        )


def chunk_by_paragraphs(text: str, min_len: int = 80) -> list[ChunkData]:
    blocks = [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]
    chunks: list[ChunkData] = []

    for block in blocks:
        if len(block) < min_len and chunks:
            previous = chunks[-1]
            merged = f"{previous.text}\n\n{block}".strip()
            chunks[-1] = ChunkData(
                chunk_index=previous.chunk_index,
                heading=previous.heading,
                section_path=previous.section_path,
                text=merged,
                text_hash=sha256_hex(merged),
            )
            continue

        append_chunk(
            chunks=chunks,
            heading="",
            section_path="",
            text=block,
        )

    return chunks


def build_section_path(
    current_path: list[str],
    kind_upper: str,
    label: str,
) -> list[str]:
    if kind_upper == "РАЗДЕЛ":
        return [label]

    if kind_upper == "ГЛАВА":
        if current_path and current_path[0].startswith("Раздел"):
            return [current_path[0], label]
        return [label]

    if kind_upper == "СТАТЬЯ":
        if len(current_path) >= 2 and current_path[1].startswith("Глава"):
            return [current_path[0], current_path[1], label]
        if current_path and current_path[0].startswith("Раздел"):
            return [current_path[0], label]
        return [label]

    if kind_upper == "ПУНКТ":
        return current_path + [label]

    return current_path + [label]


def chunk_by_structure_ru(text: str, min_len: int = 80) -> list[ChunkData]:
    """
    Делит текст по структурным заголовкам.
    В chunk попадает только тело секции, без следующего заголовка.
    Слишком большие секции делятся на несколько под-чанков.
    """
    lines = [line.rstrip() for line in text.split("\n")]

    chunks: list[ChunkData] = []
    current_path: list[str] = []
    current_heading = ""
    buffer: list[str] = []
    found_structure = False

    def flush() -> None:
        nonlocal buffer

        block_lines = [line for line in buffer if line.strip()]
        buffer = []

        if not block_lines:
            return

        block = "\n".join(block_lines).strip()
        if not block:
            return

        section_path = " > ".join(current_path)
        append_chunk(
            chunks=chunks,
            heading=current_heading,
            section_path=section_path,
            text=block,
        )

    for line in lines:
        stripped = line.strip()
        match = SECTION_RE.match(stripped)

        if match:
            found_structure = True
            flush()

            kind = match.group("kind")
            num = match.group("num")
            title = match.group("title") or ""
            label = normalize_heading_label(kind=kind, num=num, title=title)

            current_path = build_section_path(
                current_path=current_path,
                kind_upper=kind.upper(),
                label=label,
            )
            current_heading = label
            continue

        if not found_structure:
            buffer.append(line)
            continue

        if stripped and LIST_ITEM_RE.match(stripped) and buffer:
            candidate = "\n".join([part for part in buffer if part.strip()]).strip()
            if len(candidate) >= SOFT_CHUNK_LEN:
                flush()

        buffer.append(line)

    flush()

    if not found_structure or not chunks:
        return chunk_by_paragraphs(text=text, min_len=min_len)

    return chunks
