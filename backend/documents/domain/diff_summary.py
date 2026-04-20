from __future__ import annotations

from typing import Any

from .change_enrichment import (
    enrich_compare_payload,
    get_significance_label,
    select_prioritized_change_entries,
    summarize_payload_significance,
)


def truncate_text(text: str, max_len: int = 160) -> str:
    text = " ".join((text or "").split())
    if len(text) <= max_len:
        return text
    return f"{text[: max_len - 1].rstrip()}…"


def build_change_title(chunk: dict[str, Any]) -> str:
    heading = (chunk.get("heading") or "").strip()
    section_path = (chunk.get("section_path") or "").strip()

    if heading:
        return heading
    if section_path:
        return section_path
    return "Фрагмент без заголовка"


def build_brief_summary(diff_payload: dict[str, Any]) -> dict[str, Any]:
    diff_payload = enrich_compare_payload(diff_payload)
    summary = dict(diff_payload["summary"])
    significance_counts, manual_review_count = summarize_payload_significance(
        diff_payload
    )
    summary["by_significance"] = significance_counts
    summary["manual_review_count"] = manual_review_count

    lines: list[str] = []

    if summary["added"]:
        lines.append(f"Добавлено фрагментов: {summary['added']}.")
    if summary["removed"]:
        lines.append(f"Удалено фрагментов: {summary['removed']}.")
    if summary["modified"]:
        lines.append(f"Изменено фрагментов: {summary['modified']}.")
    if summary["moved"]:
        lines.append(f"Перемещено фрагментов: {summary['moved']}.")
    if summary["unchanged"]:
        lines.append(f"Без изменений: {summary['unchanged']}.")

    if significance_counts.get("critical"):
        lines.append(f"Критичных изменений: {significance_counts['critical']}.")
    if significance_counts.get("important"):
        lines.append(f"Важных изменений: {significance_counts['important']}.")
    if significance_counts.get("informational"):
        lines.append(
            f"Информационных изменений: {significance_counts['informational']}."
        )
    if significance_counts.get("editorial"):
        lines.append(
            f"Редакционных/технических изменений: {significance_counts['editorial']}."
        )
    if manual_review_count:
        lines.append(f"Требуют ручной проверки: {manual_review_count}.")

    if not lines:
        lines.append("Изменений не обнаружено.")

    highlights: list[dict[str, Any]] = []

    for change_type, payload in select_prioritized_change_entries(
        diff_payload,
        limit=3,
        prefer_non_editorial=True,
    ):
        if change_type == "added":
            highlight: dict[str, Any] = {
                "type": "added",
                "title": build_change_title(payload),
                "description": truncate_text(payload.get("text", "")),
            }
        elif change_type == "removed":
            highlight = {
                "type": "removed",
                "title": build_change_title(payload),
                "description": truncate_text(payload.get("text", "")),
            }
        elif change_type == "modified":
            new_chunk = payload["to_chunk"]
            old_chunk = payload["from_chunk"]
            highlight = {
                "type": "modified",
                "title": build_change_title(new_chunk),
                "description": (
                    f"Было: {truncate_text(old_chunk.get('text', ''), 100)} | "
                    f"Стало: {truncate_text(new_chunk.get('text', ''), 100)}"
                ),
                "similarity": payload.get("similarity"),
                "match_reason": payload.get("match_reason"),
            }
        else:
            from_chunk = payload["from_chunk"]
            to_chunk = payload["to_chunk"]
            highlight = {
                "type": "moved",
                "title": build_change_title(to_chunk),
                "description": (
                    f"Перемещён: index {from_chunk.get('chunk_index')} -> "
                    f"{to_chunk.get('chunk_index')}"
                ),
            }

        highlight["semantic_type"] = payload.get("semantic_type")
        highlight["significance_label"] = get_significance_label(payload)
        highlight["significance_reason"] = payload.get(
            "significance_reason"
        ) or payload.get("importance_explanation")
        highlight["requires_manual_review"] = bool(
            payload.get("requires_manual_review")
        )
        highlights.append(highlight)

    return {
        "from_version": diff_payload["from_version"],
        "to_version": diff_payload["to_version"],
        "identical": diff_payload["identical"],
        "summary": summary,
        "brief_text": " ".join(lines),
        "highlights": highlights,
    }
