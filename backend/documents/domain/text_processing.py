from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass

MAX_CHUNK_LEN = 2200
SOFT_CHUNK_LEN = 1400
PDF_PAGE_BREAK = "\f"

FRAGMENT_TYPE_TITLE = "title"
FRAGMENT_TYPE_PREAMBLE = "preamble"
FRAGMENT_TYPE_SECTION = "section"
FRAGMENT_TYPE_CHAPTER = "chapter"
FRAGMENT_TYPE_ARTICLE = "article"
FRAGMENT_TYPE_POINT = "point"
FRAGMENT_TYPE_SUBPOINT = "subpoint"
FRAGMENT_TYPE_PARAGRAPH = "paragraph"
FRAGMENT_TYPE_FALLBACK_BLOCK = "fallback_block"

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
    r"^(?P<kind>раздел|глава|статья)\s+"
    r"(?P<num>[0-9IVXLCА-ЯЁA-Z]+(?:\.[0-9]+)*)"
    r"(?:[.)])?\s*(?P<title>.*)$",
    re.IGNORECASE,
)
TEXTUAL_FRAGMENT_RE = re.compile(
    r"^(?P<kind>пункт|подпункт|абзац)\s+"
    r"(?P<num>[0-9IVXLCА-ЯЁA-Zа-яёa-z-]+(?:\.[0-9]+)*)"
    r"(?:[.)])?\s*(?P<title>.*)$",
    re.IGNORECASE,
)
DECIMAL_POINT_RE = re.compile(r"^(?P<label>\d+(?:\.\d+)*)\.\s*(?P<body>.*)$")
BRACKET_NUMERIC_RE = re.compile(r"^(?P<label>\d+)\)\s*(?P<body>.*)$")
LETTER_SUBPOINT_RE = re.compile(
    r"^(?P<label>[а-яёa-z])\)\s*(?P<body>.*)$",
    re.IGNORECASE,
)
LIST_ITEM_RE = re.compile(r"^\s*(?:\d+\)|\d+\.|-\s+|•\s+|[а-яА-Я]\))")
POINT_MARKER_RE = re.compile(
    r"^\s*(?:\d+(?:\.\d+)+\.?|пункт\s+\d+|подпункт\s+[а-яА-Я0-9]+|"
    r"абзац\s+[а-яА-Я0-9-]+)\b",
    re.IGNORECASE,
)

KIND_TO_FRAGMENT_TYPE = {
    "раздел": FRAGMENT_TYPE_SECTION,
    "глава": FRAGMENT_TYPE_CHAPTER,
    "статья": FRAGMENT_TYPE_ARTICLE,
    "пункт": FRAGMENT_TYPE_POINT,
    "подпункт": FRAGMENT_TYPE_SUBPOINT,
    "абзац": FRAGMENT_TYPE_PARAGRAPH,
}
KIND_TO_TITLE = {
    "раздел": "Раздел",
    "глава": "Глава",
    "статья": "Статья",
    "пункт": "Пункт",
    "подпункт": "Подпункт",
    "абзац": "Абзац",
}
FRAGMENT_LEVELS = {
    FRAGMENT_TYPE_TITLE: 0,
    FRAGMENT_TYPE_PREAMBLE: 0,
    FRAGMENT_TYPE_SECTION: 1,
    FRAGMENT_TYPE_CHAPTER: 2,
    FRAGMENT_TYPE_ARTICLE: 3,
    FRAGMENT_TYPE_POINT: 4,
    FRAGMENT_TYPE_SUBPOINT: 5,
    FRAGMENT_TYPE_PARAGRAPH: 6,
    FRAGMENT_TYPE_FALLBACK_BLOCK: 0,
}


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
    fragment_type: str = FRAGMENT_TYPE_FALLBACK_BLOCK
    structure_level: int = 0
    raw_label: str = ""
    canonical_label: str = ""
    path_key: str = ""


@dataclass(frozen=True)
class StructuralLabel:
    fragment_type: str
    raw_label: str
    canonical_label: str
    display_label: str
    path_segment: str
    structure_level: int


@dataclass(frozen=True)
class FragmentDraft:
    fragment_type: str
    raw_label: str
    canonical_label: str
    heading: str
    section_path: str
    path_key: str
    structure_level: int
    text: str


@dataclass
class PendingFragment:
    fragment_type: str
    raw_label: str
    canonical_label: str
    heading: str
    section_path: str
    path_key: str
    structure_level: int
    buffer: list[str]


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
        or TEXTUAL_FRAGMENT_RE.match(line)
        or DECIMAL_POINT_RE.match(line)
        or BRACKET_NUMERIC_RE.match(line)
        or LETTER_SUBPOINT_RE.match(line)
        or LIST_ITEM_RE.match(line)
        or POINT_MARKER_RE.match(line)
    )


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_heading_label(kind: str, num: str, title: str) -> str:
    kind_key = (kind or "").strip().lower()
    kind_title = KIND_TO_TITLE.get(kind_key, kind_key.title())
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


def _normalize_marker_for_path(value: str) -> str:
    normalized = normalize_text(value).lower()
    normalized = normalized.replace("№", "no")
    normalized = re.sub(r"[^\w.]+", "-", normalized, flags=re.UNICODE)
    normalized = re.sub(r"-+", "-", normalized, flags=re.UNICODE)
    return normalized.strip("-.")


def _normalize_marker_value(value: str) -> str:
    return normalize_text((value or "").rstrip(".)"))


def _make_structural_label(*, kind: str, num: str, title: str = "") -> StructuralLabel:
    kind_key = (kind or "").strip().lower()
    fragment_type = KIND_TO_FRAGMENT_TYPE[kind_key]
    raw_label = f"{KIND_TO_TITLE[kind_key]} {num}".strip()
    canonical_label = raw_label
    display_label = normalize_heading_label(kind=kind_key, num=num, title=title)
    path_segment = f"{fragment_type}:{_normalize_marker_for_path(num)}"
    return StructuralLabel(
        fragment_type=fragment_type,
        raw_label=raw_label,
        canonical_label=canonical_label,
        display_label=display_label,
        path_segment=path_segment,
        structure_level=FRAGMENT_LEVELS[fragment_type],
    )


def _make_numeric_marker_label(
    *,
    fragment_type: str,
    raw_label: str,
    numeric_value: str,
) -> StructuralLabel:
    normalized_value = _normalize_marker_value(numeric_value)
    kind_title = "Пункт" if fragment_type == FRAGMENT_TYPE_POINT else "Подпункт"
    canonical_label = f"{kind_title} {normalized_value}".strip()
    return StructuralLabel(
        fragment_type=fragment_type,
        raw_label=raw_label.strip(),
        canonical_label=canonical_label,
        display_label=canonical_label,
        path_segment=f"{fragment_type}:{_normalize_marker_for_path(normalized_value)}",
        structure_level=FRAGMENT_LEVELS[fragment_type],
    )


def _make_special_label(*, fragment_type: str, index: int) -> StructuralLabel:
    if fragment_type == FRAGMENT_TYPE_TITLE:
        raw_label = "Заголовок документа"
        canonical_label = raw_label
        path_segment = "title"
    elif fragment_type == FRAGMENT_TYPE_PREAMBLE:
        raw_label = f"Преамбула {index}"
        canonical_label = raw_label
        path_segment = f"preamble:{index}"
    elif fragment_type == FRAGMENT_TYPE_PARAGRAPH:
        raw_label = f"Абзац {index}"
        canonical_label = raw_label
        path_segment = f"paragraph:{index}"
    else:
        raw_label = f"Fallback block {index}"
        canonical_label = raw_label
        path_segment = f"fallback:{index}"

    return StructuralLabel(
        fragment_type=fragment_type,
        raw_label=raw_label,
        canonical_label=canonical_label,
        display_label=canonical_label,
        path_segment=path_segment,
        structure_level=FRAGMENT_LEVELS[fragment_type],
    )


def _join_path(parts: list[str]) -> str:
    return " > ".join(part for part in parts if part)


def _build_fragment_heading(
    *,
    fragment_label: StructuralLabel,
    section_label: StructuralLabel | None,
    chapter_label: StructuralLabel | None,
    article_label: StructuralLabel | None,
    point_label: StructuralLabel | None,
) -> str:
    if fragment_label.fragment_type in {
        FRAGMENT_TYPE_TITLE,
        FRAGMENT_TYPE_PREAMBLE,
        FRAGMENT_TYPE_FALLBACK_BLOCK,
    }:
        return fragment_label.display_label

    if fragment_label.fragment_type in {
        FRAGMENT_TYPE_SECTION,
        FRAGMENT_TYPE_CHAPTER,
        FRAGMENT_TYPE_ARTICLE,
    }:
        reference = article_label or chapter_label or section_label or fragment_label
        return reference.display_label

    article_heading = article_label.display_label if article_label else ""
    point_heading = point_label.canonical_label if point_label else ""

    if fragment_label.fragment_type == FRAGMENT_TYPE_POINT and article_heading:
        return f"{article_heading} · {fragment_label.canonical_label}"
    if fragment_label.fragment_type == FRAGMENT_TYPE_SUBPOINT:
        parts = [article_heading, point_heading, fragment_label.canonical_label]
        parts = [part for part in parts if part]
        return " · ".join(parts) if parts else fragment_label.canonical_label
    if fragment_label.fragment_type == FRAGMENT_TYPE_PARAGRAPH and article_heading:
        return f"{article_heading} · {fragment_label.canonical_label}"

    reference = point_label or article_label or chapter_label or section_label
    if reference is not None:
        return f"{reference.display_label} · {fragment_label.canonical_label}"

    return fragment_label.display_label


def _build_fragment_path(
    *,
    fragment_label: StructuralLabel,
    section_label: StructuralLabel | None,
    chapter_label: StructuralLabel | None,
    article_label: StructuralLabel | None,
    point_label: StructuralLabel | None,
) -> tuple[str, str]:
    display_parts: list[str] = []
    key_parts: list[str] = []

    for label in (section_label, chapter_label, article_label):
        if label is None:
            continue
        display_parts.append(label.display_label)
        key_parts.append(label.path_segment)

    if point_label is not None:
        display_parts.append(point_label.canonical_label)
        key_parts.append(point_label.path_segment)

    if fragment_label.fragment_type == FRAGMENT_TYPE_TITLE:
        return fragment_label.display_label, fragment_label.path_segment

    if fragment_label.fragment_type in {
        FRAGMENT_TYPE_PREAMBLE,
        FRAGMENT_TYPE_FALLBACK_BLOCK,
    }:
        return fragment_label.display_label, fragment_label.path_segment

    if fragment_label.fragment_type in {
        FRAGMENT_TYPE_SECTION,
        FRAGMENT_TYPE_CHAPTER,
        FRAGMENT_TYPE_ARTICLE,
    }:
        return _join_path(display_parts), "/".join(key_parts)

    display_parts.append(fragment_label.canonical_label)
    key_parts.append(fragment_label.path_segment)
    return _join_path(display_parts), "/".join(key_parts)


def append_chunk(
    chunks: list[ChunkData],
    *,
    heading: str,
    section_path: str,
    text: str,
    fragment_type: str = FRAGMENT_TYPE_FALLBACK_BLOCK,
    structure_level: int = 0,
    raw_label: str = "",
    canonical_label: str = "",
    path_key: str = "",
) -> None:
    block = text.strip()
    if not block:
        return

    pieces = split_large_block(block)
    total_parts = len(pieces)

    for offset, piece in enumerate(pieces, start=1):
        chunk_index = len(chunks) + 1
        heading_value = heading
        canonical_value = canonical_label
        path_value = path_key

        if total_parts > 1:
            part_suffix = f" (часть {offset})"
            heading_value = (
                heading_value + part_suffix if heading_value else f"Часть {offset}"
            )
            canonical_value = (
                canonical_value + part_suffix if canonical_value else f"Часть {offset}"
            )
            path_value = (
                f"{path_value}#part-{offset}" if path_value else f"part-{offset}"
            )

        chunks.append(
            ChunkData(
                chunk_index=chunk_index,
                heading=heading_value,
                section_path=section_path,
                text=piece,
                text_hash=sha256_hex(piece),
                fragment_type=fragment_type,
                structure_level=structure_level,
                raw_label=raw_label,
                canonical_label=canonical_value,
                path_key=path_value,
            )
        )


def _append_fragment(chunks: list[ChunkData], fragment: FragmentDraft) -> None:
    append_chunk(
        chunks=chunks,
        heading=fragment.heading,
        section_path=fragment.section_path,
        text=fragment.text,
        fragment_type=fragment.fragment_type,
        structure_level=fragment.structure_level,
        raw_label=fragment.raw_label,
        canonical_label=fragment.canonical_label,
        path_key=fragment.path_key,
    )


def chunk_by_paragraphs(text: str, min_len: int = 80) -> list[ChunkData]:
    blocks = [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]
    chunks: list[ChunkData] = []
    fallback_index = 0

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
                fragment_type=previous.fragment_type,
                structure_level=previous.structure_level,
                raw_label=previous.raw_label,
                canonical_label=previous.canonical_label,
                path_key=previous.path_key,
            )
            continue

        fallback_index += 1
        label = _make_special_label(
            fragment_type=FRAGMENT_TYPE_FALLBACK_BLOCK,
            index=fallback_index,
        )
        append_chunk(
            chunks=chunks,
            heading=label.display_label,
            section_path=label.display_label,
            text=block,
            fragment_type=label.fragment_type,
            structure_level=label.structure_level,
            raw_label=label.raw_label,
            canonical_label=label.canonical_label,
            path_key=label.path_segment,
        )

    return chunks


def _looks_like_document_title(block: str) -> bool:
    if not block:
        return False
    normalized = normalize_text(block)
    lines = [line for line in normalized.splitlines() if line.strip()]
    if not lines:
        return False
    if len(lines) > 3:
        return False
    if len(normalized) > 220:
        return False
    if normalized.endswith((".", ";", ":")) and len(normalized) > 120:
        return False
    return True


def _flush_pending(
    pending: PendingFragment | None,
    fragments: list[FragmentDraft],
) -> None:
    if pending is None:
        return

    block_lines = [line for line in pending.buffer if line.strip()]
    if not block_lines:
        return

    block = "\n".join(block_lines).strip()
    if not block:
        return

    fragments.append(
        FragmentDraft(
            fragment_type=pending.fragment_type,
            raw_label=pending.raw_label,
            canonical_label=pending.canonical_label,
            heading=pending.heading,
            section_path=pending.section_path,
            path_key=pending.path_key,
            structure_level=pending.structure_level,
            text=block,
        )
    )


def _flush_leading_blocks(
    *,
    lines: list[str],
    fragments: list[FragmentDraft],
    found_structure: bool,
) -> None:
    blocks = [
        block.strip()
        for block in re.split(r"\n\s*\n", "\n".join(lines))
        if block.strip()
    ]
    if not blocks:
        return

    title_taken = False
    preamble_index = 0
    for block_index, block in enumerate(blocks, start=1):
        if (
            found_structure
            and not title_taken
            and block_index == 1
            and _looks_like_document_title(block)
        ):
            label = _make_special_label(fragment_type=FRAGMENT_TYPE_TITLE, index=1)
            fragments.append(
                FragmentDraft(
                    fragment_type=label.fragment_type,
                    raw_label=label.raw_label,
                    canonical_label=label.canonical_label,
                    heading=label.display_label,
                    section_path=label.display_label,
                    path_key=label.path_segment,
                    structure_level=label.structure_level,
                    text=block,
                )
            )
            title_taken = True
            continue

        preamble_index += 1
        label = _make_special_label(
            fragment_type=FRAGMENT_TYPE_PREAMBLE,
            index=preamble_index,
        )
        fragments.append(
            FragmentDraft(
                fragment_type=label.fragment_type,
                raw_label=label.raw_label,
                canonical_label=label.canonical_label,
                heading=label.display_label,
                section_path=label.display_label,
                path_key=label.path_segment,
                structure_level=label.structure_level,
                text=block,
            )
        )


def _build_pending_from_label(
    *,
    label: StructuralLabel,
    initial_text: str,
    section_label: StructuralLabel | None,
    chapter_label: StructuralLabel | None,
    article_label: StructuralLabel | None,
    point_label: StructuralLabel | None,
) -> PendingFragment:
    heading = _build_fragment_heading(
        fragment_label=label,
        section_label=section_label,
        chapter_label=chapter_label,
        article_label=article_label,
        point_label=point_label,
    )
    section_path, path_key = _build_fragment_path(
        fragment_label=label,
        section_label=section_label,
        chapter_label=chapter_label,
        article_label=article_label,
        point_label=point_label,
    )
    buffer = [initial_text.strip()] if initial_text and initial_text.strip() else []
    return PendingFragment(
        fragment_type=label.fragment_type,
        raw_label=label.raw_label,
        canonical_label=label.canonical_label,
        heading=heading,
        section_path=section_path,
        path_key=path_key,
        structure_level=label.structure_level,
        buffer=buffer,
    )


def _match_fragment_marker(
    line: str,
    *,
    has_point_context: bool,
) -> tuple[StructuralLabel, str] | None:
    textual_match = TEXTUAL_FRAGMENT_RE.match(line)
    if textual_match:
        kind = textual_match.group("kind").lower()
        label = _make_structural_label(
            kind=kind,
            num=textual_match.group("num"),
            title="",
        )
        body = textual_match.group("title") or ""
        return label, body

    decimal_match = DECIMAL_POINT_RE.match(line)
    if decimal_match:
        numeric_value = decimal_match.group("label")
        raw_label = f"{numeric_value}."
        fragment_type = (
            FRAGMENT_TYPE_POINT if "." not in numeric_value else FRAGMENT_TYPE_SUBPOINT
        )
        label = _make_numeric_marker_label(
            fragment_type=fragment_type,
            raw_label=raw_label,
            numeric_value=numeric_value,
        )
        return label, decimal_match.group("body") or ""

    bracket_match = BRACKET_NUMERIC_RE.match(line)
    if bracket_match:
        numeric_value = bracket_match.group("label")
        label = _make_numeric_marker_label(
            fragment_type=(
                FRAGMENT_TYPE_SUBPOINT if has_point_context else FRAGMENT_TYPE_POINT
            ),
            raw_label=f"{numeric_value})",
            numeric_value=numeric_value,
        )
        return label, bracket_match.group("body") or ""

    letter_match = LETTER_SUBPOINT_RE.match(line)
    if letter_match:
        letter_value = letter_match.group("label").lower()
        label = _make_numeric_marker_label(
            fragment_type=FRAGMENT_TYPE_SUBPOINT,
            raw_label=f"{letter_value})",
            numeric_value=letter_value,
        )
        return label, letter_match.group("body") or ""

    return None


def _make_context_body_label(
    *,
    section_label: StructuralLabel | None,
    chapter_label: StructuralLabel | None,
    article_label: StructuralLabel | None,
) -> StructuralLabel:
    if article_label is not None:
        return article_label
    if chapter_label is not None:
        return chapter_label
    if section_label is not None:
        return section_label
    return _make_special_label(fragment_type=FRAGMENT_TYPE_PARAGRAPH, index=1)


def chunk_by_structure_ru(text: str, min_len: int = 80) -> list[ChunkData]:
    lines = [line.rstrip() for line in text.split("\n")]

    fragments: list[FragmentDraft] = []
    leading_lines: list[str] = []
    pending: PendingFragment | None = None
    found_structure = False

    current_section: StructuralLabel | None = None
    current_chapter: StructuralLabel | None = None
    current_article: StructuralLabel | None = None
    current_point: StructuralLabel | None = None

    for line in lines:
        stripped = line.strip()

        if not stripped:
            if pending is not None:
                pending.buffer.append("")
            elif not found_structure:
                leading_lines.append("")
            continue

        section_match = SECTION_RE.match(stripped)
        if section_match:
            if leading_lines:
                _flush_leading_blocks(
                    lines=leading_lines,
                    fragments=fragments,
                    found_structure=True,
                )
                leading_lines = []

            _flush_pending(pending, fragments)
            pending = None
            found_structure = True

            kind = section_match.group("kind").lower()
            label = _make_structural_label(
                kind=kind,
                num=section_match.group("num"),
                title=section_match.group("title") or "",
            )

            if label.fragment_type == FRAGMENT_TYPE_SECTION:
                current_section = label
                current_chapter = None
                current_article = None
                current_point = None
            elif label.fragment_type == FRAGMENT_TYPE_CHAPTER:
                current_chapter = label
                current_article = None
                current_point = None
            elif label.fragment_type == FRAGMENT_TYPE_ARTICLE:
                current_article = label
                current_point = None
            continue

        marker_match = _match_fragment_marker(
            stripped,
            has_point_context=current_point is not None,
        )
        if marker_match is not None:
            if leading_lines:
                _flush_leading_blocks(
                    lines=leading_lines,
                    fragments=fragments,
                    found_structure=True,
                )
                leading_lines = []

            _flush_pending(pending, fragments)
            pending = None
            found_structure = True

            marker_label, inline_body = marker_match
            point_context = current_point
            if marker_label.fragment_type == FRAGMENT_TYPE_POINT:
                current_point = marker_label
                point_context = None
            elif marker_label.fragment_type != FRAGMENT_TYPE_SUBPOINT:
                point_context = current_point

            pending = _build_pending_from_label(
                label=marker_label,
                initial_text=inline_body,
                section_label=current_section,
                chapter_label=current_chapter,
                article_label=current_article,
                point_label=point_context,
            )
            continue

        if not found_structure:
            leading_lines.append(line)
            continue

        if pending is None:
            base_label = _make_context_body_label(
                section_label=current_section,
                chapter_label=current_chapter,
                article_label=current_article,
            )
            pending = _build_pending_from_label(
                label=base_label,
                initial_text="",
                section_label=current_section,
                chapter_label=current_chapter,
                article_label=current_article,
                point_label=None,
            )

        pending.buffer.append(line)

        if stripped and LIST_ITEM_RE.match(stripped):
            candidate = "\n".join(
                [part for part in pending.buffer if part.strip()]
            ).strip()
            if (
                pending.fragment_type
                in {
                    FRAGMENT_TYPE_SECTION,
                    FRAGMENT_TYPE_CHAPTER,
                    FRAGMENT_TYPE_ARTICLE,
                }
                and len(candidate) >= SOFT_CHUNK_LEN
            ):
                _flush_pending(pending, fragments)
                pending = None

    if leading_lines:
        _flush_leading_blocks(
            lines=leading_lines,
            fragments=fragments,
            found_structure=found_structure,
        )

    _flush_pending(pending, fragments)

    if not found_structure or not fragments:
        return chunk_by_paragraphs(text=text, min_len=min_len)

    chunks: list[ChunkData] = []
    for fragment in fragments:
        _append_fragment(chunks, fragment)

    if not chunks:
        return chunk_by_paragraphs(text=text, min_len=min_len)

    return chunks
