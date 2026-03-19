from __future__ import annotations

from typing import Any


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
    summary = diff_payload["summary"]
    added = diff_payload["added"]
    removed = diff_payload["removed"]
    modified = diff_payload["modified"]
    moved = diff_payload["moved"]

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

    if not lines:
        lines.append("Изменений не обнаружено.")

    highlights: list[dict[str, Any]] = []

    for chunk in added[:3]:
        highlights.append(
            {
                "type": "added",
                "title": build_change_title(chunk),
                "description": truncate_text(chunk.get("text", "")),
            }
        )

    for chunk in removed[:3]:
        highlights.append(
            {
                "type": "removed",
                "title": build_change_title(chunk),
                "description": truncate_text(chunk.get("text", "")),
            }
        )

    for item in modified[:3]:
        new_chunk = item["to_chunk"]
        old_chunk = item["from_chunk"]
        highlights.append(
            {
                "type": "modified",
                "title": build_change_title(new_chunk),
                "description": (
                    f"Было: {truncate_text(old_chunk.get('text', ''), 100)} | "
                    f"Стало: {truncate_text(new_chunk.get('text', ''), 100)}"
                ),
                "similarity": item.get("similarity"),
                "match_reason": item.get("match_reason"),
            }
        )

    for item in moved[:3]:
        from_chunk = item["from_chunk"]
        to_chunk = item["to_chunk"]
        highlights.append(
            {
                "type": "moved",
                "title": build_change_title(to_chunk),
                "description": (
                    f"Перемещён: index {from_chunk.get('chunk_index')} -> "
                    f"{to_chunk.get('chunk_index')}"
                ),
            }
        )

    return {
        "from_version": diff_payload["from_version"],
        "to_version": diff_payload["to_version"],
        "identical": diff_payload["identical"],
        "summary": summary,
        "brief_text": " ".join(lines),
        "highlights": highlights,
    }
