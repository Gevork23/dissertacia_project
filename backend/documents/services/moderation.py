from __future__ import annotations

import hashlib
from typing import Any

from ..domain.diff import iter_ordered_change_entries
from ..models import DocumentVersion, ModeratedChange

RUNTIME_TO_MODERATION_LABEL = {
    "critical": ModeratedChange.Label.CRITICAL,
    "important": ModeratedChange.Label.IMPORTANT,
    "informational": ModeratedChange.Label.MINOR,
    "not_evaluated": ModeratedChange.Label.MINOR,
    "editorial": ModeratedChange.Label.IGNORED,
}

MODERATION_TO_RUNTIME_LABEL = {
    ModeratedChange.Label.CRITICAL: "critical",
    ModeratedChange.Label.IMPORTANT: "important",
    ModeratedChange.Label.MINOR: "informational",
    ModeratedChange.Label.IGNORED: "editorial",
}

MODERATION_LABEL_OPTIONS = [
    (ModeratedChange.Label.CRITICAL, "Critical"),
    (ModeratedChange.Label.IMPORTANT, "Important"),
    (ModeratedChange.Label.MINOR, "Minor"),
    (ModeratedChange.Label.IGNORED, "Ignored"),
]


def normalize_moderation_label(label: str | None) -> str:
    normalized = str(label or "").strip().lower()
    if normalized in dict(MODERATION_LABEL_OPTIONS):
        return normalized
    return ModeratedChange.Label.MINOR


def runtime_label_to_moderation(label: str | None) -> str:
    normalized = str(label or "").strip().lower()
    return RUNTIME_TO_MODERATION_LABEL.get(normalized, ModeratedChange.Label.MINOR)


def moderation_label_to_runtime(label: str | None) -> str:
    normalized = normalize_moderation_label(label)
    return MODERATION_TO_RUNTIME_LABEL[normalized]


def build_change_id(change_type: str, payload: dict[str, Any], index: int) -> str:
    old_chunk = payload.get("from_chunk") or {}
    new_chunk = payload.get("to_chunk") or {}
    basis = [
        str(index),
        str(change_type or ""),
        str(payload.get("semantic_type") or ""),
        str(payload.get("heading") or payload.get("title") or ""),
        str(payload.get("section_path") or ""),
        str(old_chunk.get("id") or ""),
        str(new_chunk.get("id") or ""),
        str(old_chunk.get("text") or payload.get("old_text") or payload.get("text") or ""),
        str(new_chunk.get("text") or payload.get("new_text") or payload.get("text") or ""),
    ]
    digest = hashlib.sha256("||".join(basis).encode("utf-8")).hexdigest()
    return digest[:64]


def annotate_diff_for_moderation(
    diff_payload: dict[str, Any],
    *,
    from_version: DocumentVersion,
    to_version: DocumentVersion,
    apply_corrections: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    moderated_rows = {
        row.change_id: row
        for row in ModeratedChange.objects.filter(
            from_version=from_version,
            to_version=to_version,
        )
    }
    moderation_rows: list[dict[str, Any]] = []

    for index, (change_type, payload) in enumerate(
        iter_ordered_change_entries(diff_payload),
        start=1,
    ):
        change_id = build_change_id(change_type, payload, index)
        auto_label = runtime_label_to_moderation(payload.get("significance_label"))
        moderated = moderated_rows.get(change_id)
        corrected_label = (
            normalize_moderation_label(moderated.corrected_label)
            if moderated is not None
            else auto_label
        )
        runtime_label = (
            moderation_label_to_runtime(corrected_label)
            if apply_corrections
            else str(payload.get("significance_label") or moderation_label_to_runtime(auto_label))
        )

        payload["change_id"] = change_id
        payload["change_type"] = change_type
        payload["original_label"] = auto_label
        payload["corrected_label"] = corrected_label
        payload["moderation_comment"] = moderated.comment if moderated is not None else ""
        payload["is_moderated"] = moderated is not None
        payload["effective_significance_label"] = runtime_label
        if apply_corrections:
            payload["significance_label"] = runtime_label

        title = (
            payload.get("title")
            or payload.get("heading")
            or (payload.get("to_chunk") or {}).get("heading")
            or (payload.get("from_chunk") or {}).get("heading")
            or payload.get("section_path")
            or (payload.get("to_chunk") or {}).get("section_path")
            or (payload.get("from_chunk") or {}).get("section_path")
            or f"Change {index}"
        )
        old_text = (
            payload.get("old_text")
            or (payload.get("from_chunk") or {}).get("text")
            or payload.get("text")
            or ""
        )
        new_text = (
            payload.get("new_text")
            or (payload.get("to_chunk") or {}).get("text")
            or payload.get("text")
            or ""
        )
        moderation_rows.append(
            {
                "index": index,
                "change_id": change_id,
                "change_type": change_type,
                "title": str(title),
                "semantic_type": str(payload.get("semantic_type") or "unclassified"),
                "original_label": auto_label,
                "corrected_label": corrected_label,
                "comment": moderated.comment if moderated is not None else "",
                "old_text": str(old_text),
                "new_text": str(new_text),
                "is_moderated": moderated is not None,
            }
        )

    return diff_payload, moderation_rows


def moderation_stats(moderation_rows: list[dict[str, Any]]) -> dict[str, int]:
    moderated = sum(1 for row in moderation_rows if row["is_moderated"])
    return {
        "total": len(moderation_rows),
        "moderated": moderated,
        "automatic": max(len(moderation_rows) - moderated, 0),
    }
