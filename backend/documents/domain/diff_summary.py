from __future__ import annotations

import re
from collections import Counter
from typing import Any

from .change_enrichment import (
    enrich_compare_payload,
    get_significance_label,
    select_prioritized_change_entries,
    summarize_payload_significance,
)

CHANGE_TYPE_LABELS = {
    "added": "Добавлено",
    "removed": "Удалено",
    "modified": "Изменено",
    "moved": "Перемещено",
}

SEMANTIC_TYPE_LABELS = {
    "deadline": "сроки",
    "document": "перечень документов",
    "obligation": "обязанности",
    "procedure": "процедурные шаги",
    "refusal": "основания отказа",
    "condition": "условия применения",
    "responsibility": "ответственность",
    "informational": "справочная информация",
    "editorial": "редакционные правки",
    "structure": "структура документа",
    "unclassified": "неклассифицированные изменения",
}

SUMMARY_PRIMARY_LABELS = {"critical", "important", "informational", "not_evaluated"}
EDITORIAL_LABELS = {"editorial"}


def truncate_text(text: str, max_len: int = 160) -> str:
    text = " ".join((text or "").split())
    if len(text) <= max_len:
        return text
    return f"{text[: max_len - 1].rstrip()}…"


def _normalize_text(text: str | None) -> str:
    text = (text or "").lower().replace("ё", "е")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _build_snippet(text: str, max_len: int = 120) -> str:
    snippet = truncate_text(text, max_len=max_len).strip()
    return snippet.rstrip(".")


def _human_join(parts: list[str]) -> str:
    unique_parts = [part for part in dict.fromkeys(parts) if part]
    if not unique_parts:
        return ""
    if len(unique_parts) == 1:
        return unique_parts[0]
    if len(unique_parts) == 2:
        return f"{unique_parts[0]} и {unique_parts[1]}"
    return ", ".join(unique_parts[:-1]) + f" и {unique_parts[-1]}"


def build_change_title(chunk: dict[str, Any]) -> str:
    heading = (chunk.get("heading") or "").strip()
    section_path = (chunk.get("section_path") or "").strip()

    if heading:
        return heading
    if section_path:
        return section_path
    return "Фрагмент без заголовка"


def _representative_chunk(change_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    if change_type in {"modified", "moved"}:
        return payload.get("to_chunk") or payload.get("from_chunk") or {}
    return payload


def _extract_text_pair(change_type: str, payload: dict[str, Any]) -> tuple[str, str]:
    if change_type == "added":
        return "", str(payload.get("text") or payload.get("new_text") or "")
    if change_type == "removed":
        return str(payload.get("text") or payload.get("old_text") or ""), ""
    if change_type in {"modified", "moved"}:
        from_chunk = payload.get("from_chunk") or {}
        to_chunk = payload.get("to_chunk") or {}
        old_text = str(payload.get("old_text") or from_chunk.get("text") or "")
        new_text = str(payload.get("new_text") or to_chunk.get("text") or "")
        return old_text, new_text
    return "", ""


def _find_entity_value(payload: dict[str, Any], entity_type: str) -> str:
    extracted_entities = payload.get("extracted_entities") or []
    if not isinstance(extracted_entities, list):
        return ""

    for entity in extracted_entities:
        if not isinstance(entity, dict):
            continue
        raw_type = _normalize_text(str(entity.get("type") or ""))
        raw_value = str(entity.get("value") or "").strip()
        if raw_type == entity_type and raw_value:
            return raw_value
    return ""


def _find_deadline_value(text: str) -> str:
    match = re.search(
        r"(\d+\s+(?:рабоч(?:их|ие)?|календарн(?:ых|ые)?)\s+дн\w*)",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return ""
    return match.group(1).strip()


def _extract_required_documents(text: str) -> str:
    match = re.search(
        r"(?:представля\w+|предоставля\w+|прилага\w+)\s+(.+)",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return ""
    return match.group(1).strip(" .")


def _build_deadline_explanation(change_type: str, payload: dict[str, Any]) -> str:
    old_text, new_text = _extract_text_pair(change_type, payload)
    old_deadline = _find_entity_value(payload, "deadline_old") or _find_deadline_value(
        old_text
    )
    new_deadline = _find_entity_value(payload, "deadline_new") or _find_deadline_value(
        new_text
    )

    if change_type == "modified" and old_deadline and new_deadline:
        old_value = re.search(r"\d+", old_deadline)
        new_value = re.search(r"\d+", new_deadline)
        if old_value and new_value:
            old_days = int(old_value.group(0))
            new_days = int(new_value.group(0))
            if new_days < old_days:
                prefix = "Срок сокращён"
            elif new_days > old_days:
                prefix = "Срок увеличен"
            else:
                prefix = "Формулировка срока уточнена"
        else:
            prefix = "Срок уточнён"
        return f"{prefix}: было {old_deadline}, стало {new_deadline}."

    if change_type == "added":
        if new_deadline:
            return f"Добавлен новый срок: {new_deadline}."
        if new_text:
            return f"Добавлено новое требование по сроку: {_build_snippet(new_text)}."
        return "Добавлено новое требование по срокам."

    if change_type == "removed":
        if old_deadline:
            return f"Исключено требование по сроку: {old_deadline}."
        if old_text:
            return f"Удалено требование по сроку: {_build_snippet(old_text)}."
        return "Удалено требование по срокам."

    return "Изменены требования по срокам."


def _build_document_explanation(change_type: str, payload: dict[str, Any]) -> str:
    old_text, new_text = _extract_text_pair(change_type, payload)
    old_documents = _find_entity_value(
        payload, "required_documents_old"
    ) or _extract_required_documents(old_text)
    new_documents = _find_entity_value(
        payload, "required_documents_new"
    ) or _extract_required_documents(new_text)

    if change_type == "modified" and old_documents and new_documents:
        return (
            "Изменён перечень требуемых документов: "
            f"было «{truncate_text(old_documents, 80)}», "
            f"стало «{truncate_text(new_documents, 80)}»."
        )

    if change_type == "added":
        if new_documents:
            return (
                "Добавлено новое требование по документам: "
                f"«{truncate_text(new_documents, 100)}»."
            )
        if new_text:
            return f"Добавлен новый пункт о документах: {_build_snippet(new_text)}."
        return "Добавлено новое требование по документам."

    if change_type == "removed":
        if old_documents:
            return (
                "Исключено требование по документам: "
                f"«{truncate_text(old_documents, 100)}»."
            )
        if old_text:
            return f"Удалён пункт о документах: {_build_snippet(old_text)}."
        return "Удалено требование по документам."

    return "Изменены требования к перечню документов."


def _build_text_backed_explanation(
    change_type: str,
    payload: dict[str, Any],
    *,
    added_phrase: str,
    modified_phrase: str,
    removed_phrase: str,
    moved_phrase: str,
) -> str:
    old_text, new_text = _extract_text_pair(change_type, payload)

    if change_type == "added":
        if new_text:
            return f"{added_phrase}: {_build_snippet(new_text)}."
        return f"{added_phrase}."

    if change_type == "removed":
        if old_text:
            return f"{removed_phrase}: {_build_snippet(old_text)}."
        return f"{removed_phrase}."

    if change_type == "moved":
        if new_text:
            return f"{moved_phrase}: {_build_snippet(new_text)}."
        return f"{moved_phrase}."

    if new_text:
        return f"{modified_phrase}: {_build_snippet(new_text)}."
    return f"{modified_phrase}."


def _build_editorial_explanation(change_type: str, payload: dict[str, Any]) -> str:
    old_text, new_text = _extract_text_pair(change_type, payload)
    source_text = new_text or old_text
    if change_type == "moved":
        return "Фрагмент перемещён в другую позицию документа без явного смыслового изменения."
    if source_text:
        return f"Редакционная или техническая правка: {_build_snippet(source_text)}."
    return "Редакционная или техническая правка без явного смыслового изменения."


def build_change_explanation(change_type: str, payload: dict[str, Any]) -> str:
    semantic_type = _normalize_text(str(payload.get("semantic_type") or ""))

    if semantic_type == "deadline":
        return _build_deadline_explanation(change_type, payload)
    if semantic_type == "document":
        return _build_document_explanation(change_type, payload)
    if semantic_type == "obligation":
        return _build_text_backed_explanation(
            change_type,
            payload,
            added_phrase="Добавлена новая обязанность",
            modified_phrase="Уточнены обязанности",
            removed_phrase="Исключена обязанность",
            moved_phrase="Перемещён фрагмент с обязанностью",
        )
    if semantic_type == "procedure":
        return _build_text_backed_explanation(
            change_type,
            payload,
            added_phrase="Добавлен новый процедурный шаг",
            modified_phrase="Изменён порядок процедуры",
            removed_phrase="Удалён процедурный шаг",
            moved_phrase="Перемещён процедурный фрагмент",
        )
    if semantic_type == "refusal":
        return _build_text_backed_explanation(
            change_type,
            payload,
            added_phrase="Добавлено новое основание для отказа",
            modified_phrase="Изменены основания для отказа",
            removed_phrase="Исключено основание для отказа",
            moved_phrase="Перемещён фрагмент об основаниях отказа",
        )
    if semantic_type == "condition":
        return _build_text_backed_explanation(
            change_type,
            payload,
            added_phrase="Добавлено новое условие предоставления услуги",
            modified_phrase="Изменены условия предоставления услуги",
            removed_phrase="Исключено условие предоставления услуги",
            moved_phrase="Перемещён фрагмент с условиями предоставления услуги",
        )
    if semantic_type == "responsibility":
        return _build_text_backed_explanation(
            change_type,
            payload,
            added_phrase="Добавлено новое положение об ответственности",
            modified_phrase="Изменены положения об ответственности",
            removed_phrase="Исключено положение об ответственности",
            moved_phrase="Перемещён фрагмент об ответственности",
        )
    if semantic_type == "informational":
        return _build_text_backed_explanation(
            change_type,
            payload,
            added_phrase="Добавлена справочная или контактная информация",
            modified_phrase="Обновлена справочная или контактная информация",
            removed_phrase="Удалена справочная или контактная информация",
            moved_phrase="Перемещён справочный блок",
        )
    if semantic_type in {"editorial", "structure"}:
        return _build_editorial_explanation(change_type, payload)

    old_text, new_text = _extract_text_pair(change_type, payload)
    if change_type == "added" and new_text:
        return f"Добавлен новый фрагмент: {_build_snippet(new_text)}."
    if change_type == "removed" and old_text:
        return f"Удалён фрагмент: {_build_snippet(old_text)}."
    if change_type == "moved" and new_text:
        return f"Фрагмент перенесён: {_build_snippet(new_text)}."
    if new_text:
        return f"Изменена формулировка: {_build_snippet(new_text)}."
    return "Изменение требует дополнительной интерпретации."


def _build_stats_lines(summary: dict[str, Any]) -> list[str]:
    significance_counts = summary.get("by_significance") or {}
    lines: list[str] = []

    if summary.get("added"):
        lines.append(f"Добавлено фрагментов: {summary['added']}.")
    if summary.get("removed"):
        lines.append(f"Удалено фрагментов: {summary['removed']}.")
    if summary.get("modified"):
        lines.append(f"Изменено фрагментов: {summary['modified']}.")
    if summary.get("moved"):
        lines.append(f"Перемещено фрагментов: {summary['moved']}.")
    if summary.get("unchanged"):
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
    if summary.get("manual_review_count"):
        lines.append(f"Требуют ручной проверки: {summary['manual_review_count']}.")

    return lines


def _build_overview_title(
    selection_scope: str, identical: bool, summary: dict[str, Any]
) -> str:
    if identical:
        return "Изменения не обнаружены"
    if selection_scope == "editorial_fallback":
        return "Редакционные изменения"
    if (summary.get("by_significance") or {}).get("critical"):
        return "Ключевые значимые изменения"
    return "Краткая выжимка изменений"


def _build_overview_text(
    *,
    summary: dict[str, Any],
    identical: bool,
    highlights: list[dict[str, Any]],
    selection_scope: str,
    truncated_highlights_count: int,
) -> str:
    total_changes = sum(
        int(summary.get(key) or 0) for key in ("added", "removed", "modified", "moved")
    )
    significance_counts = summary.get("by_significance") or {}
    significant_total = sum(
        int(significance_counts.get(label) or 0)
        for label in ("critical", "important", "informational", "not_evaluated")
    )

    lines: list[str] = []

    if identical or total_changes == 0:
        lines.append("Изменений между выбранными версиями не обнаружено.")
    elif selection_scope == "editorial_fallback":
        lines.append(
            "Выявлены только редакционные или технические правки; "
            "значимых смысловых изменений не обнаружено."
        )
    elif highlights and significant_total == 1:
        lines.append(f"Ключевое изменение: {highlights[0]['concise_explanation']}")
    else:
        semantic_focus = _human_join(
            [
                SEMANTIC_TYPE_LABELS.get(item.get("semantic_type") or "", "")
                for item in highlights[:3]
                if item.get("semantic_type") not in {"editorial", "structure"}
            ]
        )
        if significant_total:
            line = f"Выявлено {significant_total} значимых изменений."
        else:
            line = f"Выявлено {total_changes} изменений между версиями."
        if semantic_focus:
            line += f" Основные темы: {semantic_focus}."
        lines.append(line)

    if truncated_highlights_count > 0 and highlights:
        lines.append(
            "В краткую выжимку включены только наиболее приоритетные пункты; "
            f"ещё {truncated_highlights_count} изменений остались за пределами brief."
        )

    stats_lines = _build_stats_lines(summary)
    if stats_lines:
        lines.extend(stats_lines)

    if not lines:
        return "Изменений не обнаружено."
    return " ".join(lines)


def _select_summary_entries(
    diff_payload: dict[str, Any],
    *,
    limit: int,
) -> tuple[list[tuple[str, dict[str, Any]]], str, int]:
    prioritized_entries = select_prioritized_change_entries(
        diff_payload,
        prefer_non_editorial=True,
    )
    if not prioritized_entries:
        return [], "empty", 0

    primary_pool = [
        item
        for item in prioritized_entries
        if get_significance_label(item[1]) in SUMMARY_PRIMARY_LABELS
    ]
    if primary_pool:
        selected = primary_pool[:limit]
        return selected, "significant", max(len(primary_pool) - len(selected), 0)

    editorial_pool = [
        item
        for item in prioritized_entries
        if get_significance_label(item[1]) in EDITORIAL_LABELS
    ]
    editorial_limit = min(limit, 3)
    selected = editorial_pool[:editorial_limit]
    return selected, "editorial_fallback", max(len(editorial_pool) - len(selected), 0)


def build_brief_summary(
    diff_payload: dict[str, Any],
    *,
    limit: int = 5,
) -> dict[str, Any]:
    diff_payload = enrich_compare_payload(diff_payload)
    summary = dict(diff_payload["summary"])
    significance_counts, manual_review_count = summarize_payload_significance(
        diff_payload
    )
    summary["by_significance"] = significance_counts
    summary["manual_review_count"] = manual_review_count

    selected_entries, selection_scope, truncated_highlights_count = (
        _select_summary_entries(
            diff_payload,
            limit=limit,
        )
    )

    highlights: list[dict[str, Any]] = []
    for change_type, payload in selected_entries:
        title = build_change_title(_representative_chunk(change_type, payload))
        concise_explanation = build_change_explanation(change_type, payload)
        old_text, new_text = _extract_text_pair(change_type, payload)
        highlight: dict[str, Any] = {
            "type": change_type,
            "type_label": CHANGE_TYPE_LABELS.get(change_type, change_type),
            "title": title,
            "description": concise_explanation,
            "concise_explanation": concise_explanation,
            "semantic_type": payload.get("semantic_type"),
            "significance_label": get_significance_label(payload),
            "significance_reason": payload.get("significance_reason")
            or payload.get("importance_explanation"),
            "requires_manual_review": bool(payload.get("requires_manual_review")),
            "source_sort_order": payload.get("_original_order"),
            "source_change_item_id": None,
        }
        if old_text:
            highlight["old_text"] = truncate_text(old_text, 140)
        if new_text:
            highlight["new_text"] = truncate_text(new_text, 140)
        if payload.get("similarity") is not None:
            highlight["similarity"] = payload.get("similarity")
        if payload.get("match_reason"):
            highlight["match_reason"] = payload.get("match_reason")
        highlights.append(highlight)

    brief_text = _build_overview_text(
        summary=summary,
        identical=bool(diff_payload.get("identical", False)),
        highlights=highlights,
        selection_scope=selection_scope,
        truncated_highlights_count=truncated_highlights_count,
    )

    semantic_breakdown = Counter(
        item.get("semantic_type") or "unclassified" for item in highlights
    )

    return {
        "from_version": diff_payload["from_version"],
        "to_version": diff_payload["to_version"],
        "identical": diff_payload["identical"],
        "summary": summary,
        "overview_title": _build_overview_title(
            selection_scope,
            bool(diff_payload.get("identical", False)),
            summary,
        ),
        "selection_scope": selection_scope,
        "truncated_highlights_count": truncated_highlights_count,
        "brief_text": brief_text,
        "highlights": highlights,
        "highlights_by_semantic_type": dict(semantic_breakdown),
    }
