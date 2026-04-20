from __future__ import annotations

from collections import defaultdict
from difflib import SequenceMatcher, unified_diff
from typing import Any

from ..models import Chunk, DocumentVersion
from .change_classification import (
    classify_added_or_removed_chunk,
    classify_modified_chunk_pair,
    summarize_change_types,
)
from .text_processing import sha256_hex

HIGH_TEXT_SIMILARITY_THRESHOLD = 0.97
TEXT_SIMILARITY_THRESHOLD = 0.82
SECTION_PATH_SIMILARITY_THRESHOLD = 0.55

COMPARISON_UNIT_CHUNK = "chunk"
COMPARISON_UNIT_DOCUMENT_TEXT = "document_text"
MATCHING_STRATEGY_STRUCTURAL = "structural_chunks_v2"
MATCHING_STRATEGY_DOCUMENT_FALLBACK = "document_text_fallback_v1"

CHANGE_TYPE_ORDER = {
    "modified": 0,
    "added": 1,
    "removed": 2,
    "moved": 3,
}


def validate_version_pair(
    from_version: DocumentVersion,
    to_version: DocumentVersion,
) -> None:
    if from_version.document_id != to_version.document_id:
        raise ValueError("Versions must belong to the same document.")
    if from_version.id == to_version.id:
        raise ValueError("Comparison requires two different versions.")
    if from_version.version_number >= to_version.version_number:
        raise ValueError("Target version must be newer than source version.")


def serialize_chunk(chunk: Chunk) -> dict[str, Any]:
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


def _has_primary_anchor(chunk: Chunk) -> bool:
    return (
        bool(chunk.path_key)
        or bool(chunk.canonical_label)
        or bool(chunk.heading and chunk.section_path)
    )


def _anchor_key(chunk: Chunk, reason: str) -> str | None:
    fragment_type = chunk.fragment_type or ""

    if reason == "path_key" and chunk.path_key:
        return f"{fragment_type}|{chunk.path_key}"
    if reason == "canonical_label" and chunk.canonical_label:
        return f"{fragment_type}|{chunk.canonical_label}"
    if reason == "section_path" and chunk.heading and chunk.section_path:
        return f"{fragment_type}|{chunk.heading}|{chunk.section_path}"
    if reason == "same_index":
        return str(chunk.chunk_index)

    return None


def _build_synthetic_document_chunk(
    *,
    version: DocumentVersion,
    text: str,
) -> dict[str, Any]:
    return {
        "id": None,
        "chunk_index": 0,
        "fragment_type": COMPARISON_UNIT_DOCUMENT_TEXT,
        "structure_level": 0,
        "raw_label": "",
        "canonical_label": "Документ целиком",
        "path_key": f"document:{version.document_id}:version:{version.version_number}",
        "heading": f"{version.document.title} · версия {version.version_number}",
        "section_path": "Документ целиком",
        "text": text,
        "text_hash": sha256_hex(text) if text else "",
    }


def _build_comparison_meta(
    *, comparison_unit: str, matching_strategy: str
) -> dict[str, str]:
    return {
        "comparison_unit": comparison_unit,
        "matching_strategy": matching_strategy,
    }


def _build_document_text_fallback_diff(
    *,
    from_version: DocumentVersion,
    to_version: DocumentVersion,
) -> dict[str, Any]:
    from_text = from_version.normalized_text or from_version.extracted_text or ""
    to_text = to_version.normalized_text or to_version.extracted_text or ""
    text_diff = build_text_diff(from_text=from_text, to_text=to_text)

    added: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    modified: list[dict[str, Any]] = []
    moved: list[dict[str, Any]] = []
    unchanged_count = 0

    if from_text == to_text:
        unchanged_count = 1 if from_text else 0
    elif from_text and to_text:
        from_payload = _build_synthetic_document_chunk(
            version=from_version, text=from_text
        )
        to_payload = _build_synthetic_document_chunk(version=to_version, text=to_text)
        similarity = text_similarity(from_text, to_text)
        modified.append(
            {
                "from_chunk": from_payload,
                "to_chunk": to_payload,
                "similarity": round(similarity, 4),
                "match_reason": "document_text_fallback",
                "change_classification": classify_modified_chunk_pair(
                    from_chunk=from_payload,
                    to_chunk=to_payload,
                    similarity=similarity,
                    match_reason="document_text_fallback",
                ),
            }
        )
    elif to_text:
        new_payload = _build_synthetic_document_chunk(version=to_version, text=to_text)
        added.append(
            {
                **new_payload,
                "change_classification": classify_added_or_removed_chunk(
                    new_payload,
                    operation="added",
                ),
            }
        )
    elif from_text:
        old_payload = _build_synthetic_document_chunk(
            version=from_version, text=from_text
        )
        removed.append(
            {
                **old_payload,
                "change_classification": classify_added_or_removed_chunk(
                    old_payload,
                    operation="removed",
                ),
            }
        )

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
        "comparison_meta": _build_comparison_meta(
            comparison_unit=COMPARISON_UNIT_DOCUMENT_TEXT,
            matching_strategy=MATCHING_STRATEGY_DOCUMENT_FALLBACK,
        ),
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


def _pair_chunks_by_reason(
    old_items: list[Chunk],
    new_items: list[Chunk],
    *,
    reason: str,
    used_old_ids: set[int],
    used_new_ids: set[int],
) -> list[tuple[Chunk, Chunk, str]]:
    old_by_key: dict[str, list[Chunk]] = defaultdict(list)
    new_by_key: dict[str, list[Chunk]] = defaultdict(list)

    for chunk in old_items:
        if chunk.id in used_old_ids:
            continue
        key = _anchor_key(chunk, reason)
        if key:
            old_by_key[key].append(chunk)

    for chunk in new_items:
        if chunk.id in used_new_ids:
            continue
        key = _anchor_key(chunk, reason)
        if key:
            new_by_key[key].append(chunk)

    pairs: list[tuple[Chunk, Chunk, str]] = []
    for key in set(old_by_key) & set(new_by_key):
        old_group = sorted(old_by_key[key], key=lambda item: item.chunk_index)
        new_group = sorted(new_by_key[key], key=lambda item: item.chunk_index)
        for old_chunk, new_chunk in zip(old_group, new_group):
            used_old_ids.add(old_chunk.id)
            used_new_ids.add(new_chunk.id)
            pairs.append((old_chunk, new_chunk, reason))

    return pairs


def score_chunk_match(old_chunk: Chunk, new_chunk: Chunk) -> tuple[float, str | None]:
    if old_chunk.text_hash and old_chunk.text_hash == new_chunk.text_hash:
        return 0.0, None

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

    if same_path_key:
        return score, "path_key"
    if same_canonical:
        return score, "canonical_label"
    if same_section_path and similarity >= SECTION_PATH_SIMILARITY_THRESHOLD:
        return score, "section_path"
    if same_heading and same_fragment_type and similarity >= TEXT_SIMILARITY_THRESHOLD:
        return score, "heading"
    if (
        same_fragment_type
        and similarity >= HIGH_TEXT_SIMILARITY_THRESHOLD
        and abs(old_chunk.chunk_index - new_chunk.chunk_index) <= 2
    ):
        return score, "high_text_similarity"

    return 0.0, None


def pair_by_exact_hash(
    from_chunks: list[Chunk],
    to_chunks: list[Chunk],
) -> tuple[set[int], set[int], list[dict[str, Any]], int]:
    from_by_hash: dict[str, list[Chunk]] = defaultdict(list)
    to_by_hash: dict[str, list[Chunk]] = defaultdict(list)

    for chunk in from_chunks:
        from_by_hash[chunk.text_hash].append(chunk)
    for chunk in to_chunks:
        to_by_hash[chunk.text_hash].append(chunk)

    matched_from_ids: set[int] = set()
    matched_to_ids: set[int] = set()
    moved: list[dict[str, Any]] = []
    unchanged_count = 0

    for text_hash in set(from_by_hash) & set(to_by_hash):
        old_items = sorted(from_by_hash[text_hash], key=lambda item: item.chunk_index)
        new_items = sorted(to_by_hash[text_hash], key=lambda item: item.chunk_index)

        for reason in ("path_key", "canonical_label", "section_path"):
            pairs = _pair_chunks_by_reason(
                old_items,
                new_items,
                reason=reason,
                used_old_ids=matched_from_ids,
                used_new_ids=matched_to_ids,
            )
            unchanged_count += len(pairs)

        unchanged_count += len(
            _pair_chunks_by_reason(
                old_items,
                new_items,
                reason="same_index",
                used_old_ids=matched_from_ids,
                used_new_ids=matched_to_ids,
            )
        )

        remaining_old = [
            chunk for chunk in old_items if chunk.id not in matched_from_ids
        ]
        remaining_new = [chunk for chunk in new_items if chunk.id not in matched_to_ids]
        if not remaining_old or not remaining_new:
            continue

        if not any(
            _has_primary_anchor(chunk) for chunk in [*remaining_old, *remaining_new]
        ):
            for old_chunk, new_chunk in zip(remaining_old, remaining_new):
                matched_from_ids.add(old_chunk.id)
                matched_to_ids.add(new_chunk.id)
                unchanged_count += 1
            continue

        if len(remaining_old) == 1 and len(remaining_new) == 1:
            old_chunk = remaining_old[0]
            new_chunk = remaining_new[0]
            matched_from_ids.add(old_chunk.id)
            matched_to_ids.add(new_chunk.id)
            # For MVP we treat exact-text renumbering/reordering as unchanged.
            # This avoids noisy `moved` signals when a new point is inserted and
            # existing provisions are only shifted structurally.
            unchanged_count += 1

    return matched_from_ids, matched_to_ids, moved, unchanged_count


def _make_modified_item(
    *,
    old_chunk: Chunk,
    new_chunk: Chunk,
    similarity: float,
    reason: str,
) -> dict[str, Any]:
    from_payload = serialize_chunk(old_chunk)
    to_payload = serialize_chunk(new_chunk)
    return {
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


def pair_modified_by_primary_anchor(
    from_chunks: list[Chunk],
    to_chunks: list[Chunk],
) -> tuple[set[int], set[int], list[dict[str, Any]]]:
    used_old_ids: set[int] = set()
    used_new_ids: set[int] = set()
    modified: list[dict[str, Any]] = []

    for reason in ("path_key", "canonical_label", "section_path"):
        pairs = _pair_chunks_by_reason(
            from_chunks,
            to_chunks,
            reason=reason,
            used_old_ids=used_old_ids,
            used_new_ids=used_new_ids,
        )
        for old_chunk, new_chunk, pair_reason in pairs:
            modified.append(
                _make_modified_item(
                    old_chunk=old_chunk,
                    new_chunk=new_chunk,
                    similarity=text_similarity(old_chunk.text, new_chunk.text),
                    reason=pair_reason,
                )
            )

    return used_old_ids, used_new_ids, modified


def pair_modified_chunks(
    from_chunks: list[Chunk],
    to_chunks: list[Chunk],
) -> tuple[set[int], set[int], list[dict[str, Any]]]:
    candidates: list[tuple[float, Chunk, Chunk, float, str]] = []

    for old_chunk in from_chunks:
        for new_chunk in to_chunks:
            score, reason = score_chunk_match(old_chunk=old_chunk, new_chunk=new_chunk)
            if score <= 0 or reason is None:
                continue
            candidates.append(
                (
                    score,
                    old_chunk,
                    new_chunk,
                    text_similarity(old_chunk.text, new_chunk.text),
                    reason,
                )
            )

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
    modified: list[dict[str, Any]] = []

    for _, old_chunk, new_chunk, similarity, reason in candidates:
        if old_chunk.id in used_old_ids or new_chunk.id in used_new_ids:
            continue
        used_old_ids.add(old_chunk.id)
        used_new_ids.add(new_chunk.id)
        modified.append(
            _make_modified_item(
                old_chunk=old_chunk,
                new_chunk=new_chunk,
                similarity=similarity,
                reason=reason,
            )
        )

    return used_old_ids, used_new_ids, modified


def _chunk_sort_identity(chunk: dict[str, Any] | None) -> tuple[int, str, str]:
    if not chunk:
        return (0, "", "")
    chunk_index = int(chunk.get("chunk_index") or 0)
    anchor = (
        chunk.get("path_key") or chunk.get("section_path") or chunk.get("heading") or ""
    )
    label = chunk.get("canonical_label") or chunk.get("raw_label") or ""
    return (chunk_index, anchor, label)


def iter_ordered_change_entries(
    diff_payload: dict[str, Any],
) -> list[tuple[str, dict[str, Any]]]:
    entries: list[tuple[str, dict[str, Any]]] = []
    entries.extend(("added", chunk) for chunk in diff_payload.get("added", []))
    entries.extend(("modified", item) for item in diff_payload.get("modified", []))
    entries.extend(("removed", chunk) for chunk in diff_payload.get("removed", []))
    entries.extend(("moved", item) for item in diff_payload.get("moved", []))

    def _sort_key(entry: tuple[str, dict[str, Any]]) -> tuple[int, str, int, str]:
        change_type, payload = entry
        if change_type in {"modified", "moved"}:
            primary = payload.get("to_chunk") or payload.get("from_chunk") or {}
            secondary = payload.get("from_chunk") or {}
        else:
            primary = payload
            secondary = {}
        primary_index, primary_anchor, primary_label = _chunk_sort_identity(primary)
        secondary_index, _, _ = _chunk_sort_identity(secondary)
        return (
            primary_index,
            primary_anchor,
            CHANGE_TYPE_ORDER[change_type],
            f"{secondary_index:08d}:{primary_label}",
        )

    return sorted(entries, key=_sort_key)


def build_version_diff(
    from_version: DocumentVersion,
    to_version: DocumentVersion,
) -> dict[str, Any]:
    validate_version_pair(from_version=from_version, to_version=to_version)

    from_chunks = list(from_version.chunks.order_by("chunk_index"))
    to_chunks = list(to_version.chunks.order_by("chunk_index"))
    if not from_chunks or not to_chunks:
        return _build_document_text_fallback_diff(
            from_version=from_version,
            to_version=to_version,
        )

    matched_from_ids, matched_to_ids, moved, unchanged_count = pair_by_exact_hash(
        from_chunks=from_chunks,
        to_chunks=to_chunks,
    )

    unmatched_from = [
        chunk for chunk in from_chunks if chunk.id not in matched_from_ids
    ]
    unmatched_to = [chunk for chunk in to_chunks if chunk.id not in matched_to_ids]

    anchored_from_ids, anchored_to_ids, anchored_modified = (
        pair_modified_by_primary_anchor(
            from_chunks=unmatched_from,
            to_chunks=unmatched_to,
        )
    )
    unmatched_from = [
        chunk for chunk in unmatched_from if chunk.id not in anchored_from_ids
    ]
    unmatched_to = [chunk for chunk in unmatched_to if chunk.id not in anchored_to_ids]

    modified_from_ids, modified_to_ids, fallback_modified = pair_modified_chunks(
        from_chunks=unmatched_from,
        to_chunks=unmatched_to,
    )
    modified = anchored_modified + fallback_modified

    remaining_from = [
        chunk for chunk in unmatched_from if chunk.id not in modified_from_ids
    ]
    remaining_to = [chunk for chunk in unmatched_to if chunk.id not in modified_to_ids]

    removed: list[dict[str, Any]] = []
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

    added: list[dict[str, Any]] = []
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
        "comparison_meta": _build_comparison_meta(
            comparison_unit=COMPARISON_UNIT_CHUNK,
            matching_strategy=MATCHING_STRATEGY_STRUCTURAL,
        ),
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
