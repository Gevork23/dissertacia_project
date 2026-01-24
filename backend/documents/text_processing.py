# backend/documents/text_processing.py
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


def normalize_text(text: str) -> str:
    """
    Lightweight normalization for regulatory texts.
    Keeps meaning, improves diff/search stability.
    """
    if not text:
        return ""

    # unify line endings
    t = text.replace("\r\n", "\n").replace("\r", "\n")

    # normalize dashes
    t = t.replace("—", "-").replace("–", "-")

    # remove excessive spaces around newlines
    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"\n[ \t]+", "\n", t)

    # collapse 3+ newlines to 2
    t = re.sub(r"\n{3,}", "\n\n", t)

    # collapse multiple spaces/tabs
    t = re.sub(r"[ \t]{2,}", " ", t)

    return t.strip()


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ChunkData:
    chunk_index: int
    heading: str
    section_path: str
    text: str
    text_hash: str


def chunk_by_paragraphs(text: str, min_len: int = 50) -> list[ChunkData]:
    """
    MVP chunker: split by empty lines.
    Later we will add structure-aware chunking.
    """
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    chunks: list[ChunkData] = []
    idx = 1

    for b in blocks:
        if len(b) < min_len:
            # attach short blocks to previous chunk if possible
            if chunks:
                prev = chunks[-1]
                merged_text = f"{prev.text}\n\n{b}".strip()
                chunks[-1] = ChunkData(
                    chunk_index=prev.chunk_index,
                    heading=prev.heading,
                    section_path=prev.section_path,
                    text=merged_text,
                    text_hash=sha256_hex(merged_text),
                )
            else:
                chunks.append(
                    ChunkData(
                        chunk_index=idx,
                        heading="",
                        section_path="",
                        text=b,
                        text_hash=sha256_hex(b),
                    )
                )
                idx += 1
            continue

        chunks.append(
            ChunkData(
                chunk_index=idx,
                heading="",
                section_path="",
                text=b,
                text_hash=sha256_hex(b),
            )
        )
        idx += 1

    return chunks


SECTION_RE = re.compile(
    r"^(?P<kind>РАЗДЕЛ|ГЛАВА|СТАТЬЯ|Статья|Пункт|ПУНКТ)\s+(?P<num>[0-9IVXLC]+(?:\.[0-9]+)*)\.?\s*(?P<title>.*)$"
)

def chunk_by_structure_ru(text: str, min_len: int = 80) -> list[ChunkData]:
    """
    RU structure-aware chunking: tries to split by headings like:
    - РАЗДЕЛ I ...
    - ГЛАВА 2 ...
    - Статья 5. ...
    - Пункт 5.1 ...
    If no structure found -> fallback to paragraphs.
    """
    lines = [ln.rstrip() for ln in text.split("\n")]
    found_structure = False

    current_path: list[str] = []
    current_heading = ""
    buf: list[str] = []

    chunks: list[ChunkData] = []
    idx = 1

    def flush():
        nonlocal idx, buf, current_heading
        block = "\n".join([b for b in buf if b.strip()]).strip()
        if not block:
            buf = []
            return

        # If too small, merge ONLY when there is no structural heading.
        # Structural blocks (e.g., "Статья 3") must stay separate even if short.
        if len(block) < min_len and chunks and not current_heading:
            prev = chunks[-1]
            merged_text = f"{prev.text}\n\n{block}".strip()
            chunks[-1] = ChunkData(
                chunk_index=prev.chunk_index,
                heading=prev.heading,
                section_path=prev.section_path,
                text=merged_text,
                text_hash=sha256_hex(merged_text),
            )
        else:
            section_path = " > ".join(current_path)
            chunks.append(
                ChunkData(
                    chunk_index=idx,
                    heading=current_heading,
                    section_path=section_path,
                    text=block,
                    text_hash=sha256_hex(block),
                )
            )
            idx += 1


    for ln in lines:
        m = SECTION_RE.match(ln.strip())
        if m:
            found_structure = True
            # new section starts -> flush previous buffer
            flush()

            kind = m.group("kind").upper()
            num = m.group("num")
            title = (m.group("title") or "").strip()
            label = f"{kind.title()} {num}".strip()
            if title:
                label = f"{label}: {title}"

            # update path level
            if kind in ("РАЗДЕЛ",):
                current_path = [label]
            elif kind in ("ГЛАВА",):
                # keep section if exists
                if current_path:
                    current_path = [current_path[0], label]
                else:
                    current_path = [label]
            elif kind in ("СТАТЬЯ",):
                # Keep only higher levels (Раздел / Глава), replace current article level
                # Patterns we support:
                # [] -> [Статья]
                # [Раздел] -> [Раздел, Статья]
                # [Раздел, Глава] -> [Раздел, Глава, Статья]
                # [Раздел, Статья] -> [Раздел, Статья] (replace)
                # [Раздел, Глава, Статья] -> [Раздел, Глава, Статья] (replace)
                if len(current_path) >= 2 and current_path[1].startswith("Глава"):
                    # [Раздел, Глава, ...] -> keep first two
                    current_path = [current_path[0], current_path[1], label]
                elif len(current_path) >= 1 and current_path[0].startswith("Раздел"):
                    # [Раздел, ...] -> keep only Раздел
                    current_path = [current_path[0], label]
                else:
                    current_path = [label]
            elif kind in ("ПУНКТ", "ПУНКТ".title()):
                # пункт внутри статьи
                base = current_path[:]
                current_path = base + [label]

            current_heading = label
            continue

        buf.append(ln)

    flush()

    if not found_structure:
        return chunk_by_paragraphs(text)

    # fallback if structure produced nothing
    return chunks if chunks else chunk_by_paragraphs(text)
