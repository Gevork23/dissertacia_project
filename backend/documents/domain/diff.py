from __future__ import annotations

from collections import defaultdict
from difflib import SequenceMatcher, unified_diff

from ..models import Chunk, DocumentVersion
from .change_classification import (
    classify_added_or_removed_chunk,
    classify_modified_chunk_pair,
    classify_moved_chunk_pair,
    summarize_change_types,
)

HIGH_TEXT_SIMILARITY_THRESHOLD = 0.92
TEXT_SIMILARITY_THRESHOLD = 0.80
SECTION_PATH_SIMILARITY_THRESHOLD = 0.45


def serialize_chunk(chunk: Chunk) -> dict[str, str | int]:
    return {
        "id": chunk.id,
        "chunk_index": chunk.chunk_index,
        "fragment_type": chunk.fragment_type,
        "structure_level": chunk.structure_level,
        "raw_label": chunk.raw_label,
        "canonical_label": chunk.canonical_label,
        "path_key": chunk.path_key,
        "heading": chunk.heading,
        "section_path": chunk.section_path,
        "text": chunk.text,
        "text_hash": chunk.text_hash,
    }


def build_text_diff(from_text: str, to_text: str) -> str:
    return "\n".join(
        unified_diff(
            from_text.splitlines(),
            to_text.splitlines(),
            fromfile="from_version",
            tofile="to_version",
            lineterm="",
        )
    )


def text_similarity(left: str, right: str) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def get_index_proximity_score(old_chunk: Chunk, new_chunk: Chunk) -> float:
    distance = abs(old_chunk.chunk_index - new_chunk.chunk_index)
    if distance == 0:
        return 0.10
    if distance == 1:
        return 0.07
    if distance <= 3:
        return 0.03
    return 0.0


def _same_path_key(old_chunk: Chunk, new_chunk: Chunk) -> bool:
    return bool(old_chunk.path_key) and old_chunk.path_key == new_chunk.path_key


def _same_canonical_label(old_chunk: Chunk, new_chunk: Chunk) -> bool:
    return (
        bool(old_chunk.canonical_label)
        and old_chunk.canonical_label == new_chunk.canonical_label
        and old_chunk.fragment_type == new_chunk.fragment_type
    )


def _same_heading(old_chunk: Chunk, new_chunk: Chunk) -> bool:
    return bool(old_chunk.heading) and old_chunk.heading == new_chunk.heading


def _same_section_path(old_chunk: Chunk, new_chunk: Chunk) -> bool:
    return (
        bool(old_chunk.section_path)
        and old_chunk.section_path == new_chunk.section_path
    )


def _same_fragment_identity(old_chunk: Chunk, new_chunk: Chunk) -> bool:
    same_anchor = (
        _same_path_key(old_chunk, new_chunk)
        or _same_canonical_label(old_chunk, new_chunk)
        or (
            _same_heading(old_chunk, new_chunk)
            and _same_section_path(old_chunk, new_chunk)
        )
    )
    return same_anchor and old_chunk.chunk_index == new_chunk.chunk_index


def score_chunk_match(old_chunk: Chunk, new_chunk: Chunk) -> tuple[float, str | None]:
    similarity = text_similarity(old_chunk.text, new_chunk.text)
    score = similarity + get_index_proximity_score(old_chunk, new_chunk)

    same_path_key = _same_path_key(old_chunk, new_chunk)
    same_canonical = _same_canonical_label(old_chunk, new_chunk)
    same_section_path = _same_section_path(old_chunk, new_chunk)
    same_heading = _same_heading(old_chunk, new_chunk)
    same_fragment_type = old_chunk.fragment_type == new_chunk.fragment_type

    if same_fragment_type:
        score += 0.05
    if same_path_key:
        score += 0.45
    elif same_canonical:
        score += 0.30
    elif same_section_path:
        score += 0.20

    if same_heading:
        score += 0.10

    if same_path_key and similarity >= 0.20:
        return score, "path_key"

    if same_canonical and similarity >= 0.30:
        return score, "canonical_label"

    if same_section_path and similarity >= SECTION_PATH_SIMILARITY_THRESHOLD:
        return score, "section_path"

    if same_heading and same_fragment_type and similarity >= TEXT_SIMILARITY_THRESHOLD:
        return score, "heading"

    if similarity >= HIGH_TEXT_SIMILARITY_THRESHOLD:
        return score, "high_text_similarity"

    return 0.0, None


def pair_by_exact_hash(
    from_chunks: list[Chunk],
    to_chunks: list[Chunk],
) -> tuple[set[int], set[int], list[dict], int]:
    from_by_hash: dict[str, list[Chunk]] = defaultdict(list)
    to_by_hash: dict[str, list[Chunk]] = defaultdict(list)

    for chunk in from_chunks:
        from_by_hash[chunk.text_hash].append(chunk)

    for chunk in to_chunks:
        to_by_hash[chunk.text_hash].append(chunk)

    matched_from_ids: set[int] = set()
    matched_to_ids: set[int] = set()
    moved: list[dict] = []
    unchanged_count = 0

    common_hashes = set(from_by_hash) & set(to_by_hash)

    for text_hash in common_hashes:
        old_items = sorted(from_by_hash[text_hash], key=lambda item: item.chunk_index)
        new_items = sorted(to_by_hash[text_hash], key=lambda item: item.chunk_index)
        pairs_count = min(len(old_items), len(new_items))

        for index in range(pairs_count):
            old_chunk = old_items[index]
            new_chunk = new_items[index]

            matched_from_ids.add(old_chunk.id)
            matched_to_ids.add(new_chunk.id)

            if _same_fragment_identity(old_chunk, new_chunk):
                unchanged_count += 1
                continue

            from_payload = serialize_chunk(old_chunk)
            to_payload = serialize_chunk(new_chunk)

            moved.append(
                {
                    "from_chunk": from_payload,
                    "to_chunk": to_payload,
                    "change_classification": classify_moved_chunk_pair(
                        from_chunk=from_payload,
                        to_chunk=to_payload,
                    ),
                }
            )

    return matched_from_ids, matched_to_ids, moved, unchanged_count


def pair_modified_chunks(
    from_chunks: list[Chunk],
    to_chunks: list[Chunk],
) -> tuple[set[int], set[int], list[dict]]:
    candidates: list[tuple[float, Chunk, Chunk, float, str]] = []

    for old_chunk in from_chunks:
        for new_chunk in to_chunks:
            score, reason = score_chunk_match(
                old_chunk=old_chunk,
                new_chunk=new_chunk,
            )
            if score <= 0 or reason is None:
                continue

            similarity = text_similarity(old_chunk.text, new_chunk.text)
            candidates.append((score, old_chunk, new_chunk, similarity, reason))

    candidates.sort(
        key=lambda item: (
            item[0],
            item[3],
            -abs(item[1].chunk_index - item[2].chunk_index),
        ),
        reverse=True,
    )

    used_old_ids: set[int] = set()
    used_new_ids: set[int] = set()
    modified: list[dict] = []

    for _, old_chunk, new_chunk, similarity, reason in candidates:
        if old_chunk.id in used_old_ids or new_chunk.id in used_new_ids:
            continue

        used_old_ids.add(old_chunk.id)
        used_new_ids.add(new_chunk.id)

        from_payload = serialize_chunk(old_chunk)
        to_payload = serialize_chunk(new_chunk)

        modified.append(
            {
                "from_chunk": from_payload,
                "to_chunk": to_payload,
                "similarity": round(similarity, 4),
                "match_reason": reason,
                "change_classification": classify_modified_chunk_pair(
                    from_chunk=from_payload,
                    to_chunk=to_payload,
                    similarity=similarity,
                    match_reason=reason,
                ),
            }
        )

    return used_old_ids, used_new_ids, modified


def build_version_diff(
    from_version: DocumentVersion,
    to_version: DocumentVersion,
) -> dict:
    from_chunks = list(from_version.chunks.order_by("chunk_index"))
    to_chunks = list(to_version.chunks.order_by("chunk_index"))

    matched_from_ids, matched_to_ids, moved, unchanged_count = pair_by_exact_hash(
        from_chunks=from_chunks,
        to_chunks=to_chunks,
    )

    unmatched_from = [
        chunk for chunk in from_chunks if chunk.id not in matched_from_ids
    ]
    unmatched_to = [chunk for chunk in to_chunks if chunk.id not in matched_to_ids]

    modified_from_ids, modified_to_ids, modified = pair_modified_chunks(
        from_chunks=unmatched_from,
        to_chunks=unmatched_to,
    )

    remaining_from = [
        chunk for chunk in unmatched_from if chunk.id not in modified_from_ids
    ]
    remaining_to = [chunk for chunk in unmatched_to if chunk.id not in modified_to_ids]

    removed = []
    for chunk in remaining_from:
        chunk_payload = serialize_chunk(chunk)
        removed.append(
            {
                **chunk_payload,
                "change_classification": classify_added_or_removed_chunk(
                    chunk_payload,
                    operation="removed",
                ),
            }
        )

    added = []
    for chunk in remaining_to:
        chunk_payload = serialize_chunk(chunk)
        added.append(
            {
                **chunk_payload,
                "change_classification": classify_added_or_removed_chunk(
                    chunk_payload,
                    operation="added",
                ),
            }
        )

    from_text = from_version.normalized_text or from_version.extracted_text or ""
    to_text = to_version.normalized_text or to_version.extracted_text or ""
    text_diff = build_text_diff(from_text=from_text, to_text=to_text)

    identical = not added and not removed and not modified and not moved

    diff_payload = {
        "from_version": {
            "id": from_version.id,
            "document_id": from_version.document_id,
            "version_number": from_version.version_number,
            "created_at": from_version.created_at,
        },
        "to_version": {
            "id": to_version.id,
            "document_id": to_version.document_id,
            "version_number": to_version.version_number,
            "created_at": to_version.created_at,
        },
        "identical": identical,
        "summary": {
            "added": len(added),
            "removed": len(removed),
            "modified": len(modified),
            "moved": len(moved),
            "unchanged": unchanged_count,
        },
        "added": added,
        "removed": removed,
        "modified": modified,
        "moved": moved,
        "text_diff": text_diff,
    }

    diff_payload["summary"]["by_type"] = summarize_change_types(diff_payload)

    return diff_payload
