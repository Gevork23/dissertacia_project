from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass

MAX_CHUNK_LEN = 2200
SOFT_CHUNK_LEN = 1400
PDF_PAGE_BREAK = "\f"

SPACE_TRANSLATION = str.maketrans(
    {
        "\xa0": " ",
        "\u2002": " ",
        "\u2003": " ",
        "\u2007": " ",
        "\u2009": " ",
        "\u202f": " ",
    }
)
DASH_TRANSLATION = str.maketrans(
    {
        "—": "-",
        "–": "-",
        "‒": "-",
        "−": "-",
        "‑": "-",
    }
)
ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\u2060\ufeff]")
CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
PDF_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0e-\x1f\x7f]")
PDF_STAMP_LINE_RE = re.compile(r"^\[(?:[A-Z0-9_:-]{6,})\]$")
PDF_PAGE_NUMBER_TEMPLATE = (
    r"^(?:стр(?:аница)?\.?\s*{page}|page\s*{page}|p\.\s*{page}|{page})$"
)

SECTION_RE = re.compile(
    r"^(?P<kind>РАЗДЕЛ|Раздел|ГЛАВА|Глава|СТАТЬЯ|Статья|ПУНКТ|Пункт)\s+"
    r"(?P<num>[0-9IVXLC]+(?:\.[0-9]+)*)\.?\s*(?P<title>.*)$"
)
LIST_ITEM_RE = re.compile(r"^\s*(?:\d+\)|\d+\.|-\s+|•\s+|[а-яА-Я]\))")
POINT_MARKER_RE = re.compile(
    r"^\s*(?:\d+(?:\.\d+)+\.?|пункт\s+\d+|подпункт\s+[а-яА-Я0-9]+|"
    r"абзац\s+[а-яА-Я0-9-]+)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class MaterializedDocumentText:
    normalized_text: str
    content_hash: str


@dataclass(frozen=True)
class ChunkData:
    chunk_index: int
    heading: str
    section_path: str
    text: str
    text_hash: str


def normalize_text(text: str) -> str:
    if not text:
        return ""

    text = unicodedata.normalize("NFC", text)
    text = text.translate(SPACE_TRANSLATION)
    text = text.translate(DASH_TRANSLATION)
    text = text.replace("\ufeff", "")
    text = text.replace("\u00ad", "")
    text = text.replace("\u2028", "\n").replace("\u2029", "\n")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace(PDF_PAGE_BREAK, "\n\n")
    text = ZERO_WIDTH_RE.sub("", text)
    text = CONTROL_CHAR_RE.sub("", text)

    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def normalize_document_text(text: str, *, extension: str = "") -> str:
    extension = (extension or "").lower()

    if extension == ".pdf":
        return _normalize_pdf_text(text)

    return normalize_text(text)


def materialize_document_text(
    extracted_text: str,
    *,
    extension: str = "",
) -> MaterializedDocumentText:
    normalized_text = normalize_document_text(extracted_text, extension=extension)
    return MaterializedDocumentText(
        normalized_text=normalized_text,
        content_hash=sha256_hex(normalized_text),
    )


def _normalize_pdf_text(text: str) -> str:
    prepared = _prepare_pdf_text(text)
    pages = [page.strip() for page in prepared.split(PDF_PAGE_BREAK)]
    pages = [page for page in pages if page]
    if not pages:
        return ""

    repeated_top_lines = _collect_repeated_edge_lines(pages, from_top=True)
    repeated_bottom_lines = _collect_repeated_edge_lines(pages, from_top=False)

    cleaned_pages: list[str] = []
    for index, page in enumerate(pages, start=1):
        cleaned_pages.append(
            _normalize_pdf_page(
                page,
                page_number=index,
                repeated_top_lines=repeated_top_lines,
                repeated_bottom_lines=repeated_bottom_lines,
            )
        )

    joined = "\n".join(page for page in cleaned_pages if page)
    joined = _merge_hyphenated_word_breaks(joined)
    joined = _merge_wrapped_lines(joined)
    return normalize_text(joined)


def _prepare_pdf_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text or "")
    text = text.translate(SPACE_TRANSLATION)
    text = text.translate(DASH_TRANSLATION)
    text = text.replace("\ufeff", "")
    text = text.replace("\u00ad", "")
    text = text.replace("\u2028", "\n").replace("\u2029", "\n")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = ZERO_WIDTH_RE.sub("", text)
    text = PDF_CONTROL_CHAR_RE.sub("", text)
    text = re.sub(r"\n*\f\n*", PDF_PAGE_BREAK, text)
    return text.strip()


def _collect_repeated_edge_lines(
    pages: list[str],
    *,
    from_top: bool,
    edge_size: int = 6,
) -> set[str]:
    if len(pages) < 2:
        return set()

    counts: dict[str, int] = {}
    for page in pages:
        lines = [_normalize_pdf_edge_line(line) for line in page.split("\n")]
        lines = [line for line in lines if line]
        edge_lines = lines[:edge_size] if from_top else lines[-edge_size:]

        for line in set(edge_lines):
            if len(line) < 3 or len(line) > 160:
                continue
            if PDF_STAMP_LINE_RE.match(line):
                continue
            counts[line] = counts.get(line, 0) + 1

    return {line for line, count in counts.items() if count >= 2}


def _normalize_pdf_edge_line(line: str) -> str:
    return normalize_text(line).strip()


def _normalize_pdf_page(
    page: str,
    *,
    page_number: int,
    repeated_top_lines: set[str],
    repeated_bottom_lines: set[str],
) -> str:
    raw_lines = [normalize_text(line) for line in page.split("\n")]
    kept_lines: list[str] = []
    non_empty_lines = [line for line in raw_lines if line]
    total_non_empty = len(non_empty_lines)

    if total_non_empty == 0:
        return ""

    for index, line in enumerate(non_empty_lines):
        if _should_drop_pdf_line(
            line=line,
            index=index,
            total_lines=total_non_empty,
            page_number=page_number,
            repeated_top_lines=repeated_top_lines,
            repeated_bottom_lines=repeated_bottom_lines,
        ):
            continue
        kept_lines.append(line)

    return normalize_text("\n".join(kept_lines))


def _should_drop_pdf_line(
    *,
    line: str,
    index: int,
    total_lines: int,
    page_number: int,
    repeated_top_lines: set[str],
    repeated_bottom_lines: set[str],
) -> bool:
    if not line:
        return True
    if PDF_STAMP_LINE_RE.match(line):
        return True

    near_top = index < 6
    near_bottom = (total_lines - index) <= 6

    if near_top and line in repeated_top_lines:
        return True
    if near_bottom and line in repeated_bottom_lines:
        return True
    if (near_top or near_bottom) and _is_pdf_page_number_line(line, page_number):
        return True

    return False


def _is_pdf_page_number_line(line: str, page_number: int) -> bool:
    page_re = re.compile(
        PDF_PAGE_NUMBER_TEMPLATE.format(page=page_number), re.IGNORECASE
    )
    return bool(page_re.match(line.strip()))


def _merge_hyphenated_word_breaks(text: str) -> str:
    return re.sub(r"(?<=[0-9A-Za-zА-Яа-яЁё])-\n(?=[a-zа-яё])", "", text)


def _merge_wrapped_lines(text: str) -> str:
    lines = text.split("\n")
    merged_lines: list[str] = []
    buffer = ""

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if buffer:
                merged_lines.append(buffer.strip())
                buffer = ""
            if merged_lines and merged_lines[-1] != "":
                merged_lines.append("")
            continue

        if not buffer:
            buffer = stripped
            continue

        if _should_merge_wrapped_lines(buffer, stripped):
            buffer = f"{buffer.rstrip()} {stripped.lstrip()}".strip()
            continue

        merged_lines.append(buffer.strip())
        buffer = stripped

    if buffer:
        merged_lines.append(buffer.strip())

    return "\n".join(merged_lines)


def _should_merge_wrapped_lines(previous: str, current: str) -> bool:
    if _looks_like_structural_line(current):
        return False

    previous = previous.rstrip()
    current = current.lstrip()
    if not previous or not current:
        return False

    if previous.endswith((".", ";", "!", "?")):
        return False
    if previous.endswith("-"):
        return False
    if previous.endswith(":") and not _starts_with_sentence_continuation(current):
        return False
    if len(previous) < 35 and not previous.endswith((",", ":", "(", "/")):
        return False

    return _starts_with_sentence_continuation(current)


def _starts_with_sentence_continuation(text: str) -> bool:
    return bool(re.match(r"^[a-zа-яё(\[«\"']", text))


def _looks_like_structural_line(line: str) -> bool:
    return bool(
        SECTION_RE.match(line)
        or LIST_ITEM_RE.match(line)
        or POINT_MARKER_RE.match(line)
    )


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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

        append_chunk(chunks=chunks, heading="", section_path="", text=block)

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
