from __future__ import annotations

import json
import re
from typing import Any, Mapping

from ..services.importance import LABEL_PRIORITY, classify_change_importance

KNOWN_CHANGE_TYPES = {
    "deadline",
    "document",
    "obligation",
    "procedure",
    "refusal",
    "condition",
    "responsibility",
    "informational",
    "editorial",
    "structure",
    "unclassified",
}

SIGNIFICANCE_LABELS = (
    "critical",
    "important",
    "informational",
    "editorial",
    "not_evaluated",
)


def _normalize_text(text: str | None) -> str:
    text = (text or "").lower().replace("ё", "е")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, dict):
        for key in (
            "text",
            "content",
            "normalized_text",
            "body",
            "value",
            "extracted_text",
        ):
            if key in value and value[key]:
                return _stringify(value[key])
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return " ".join(_stringify(item) for item in value if item is not None)
    return str(value)


def _first_nonempty(mapping: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = mapping.get(key)
        text = _stringify(value).strip()
        if text:
            return text
    return ""


def _build_diff_text(old_text: str, new_text: str) -> str:
    return f"OLD: {old_text}\nNEW: {new_text}"


def extract_change_texts(change: Mapping[str, Any]) -> tuple[str, str, str]:
    old_text = _first_nonempty(
        change,
        "old_text",
        "before_text",
        "old_content",
        "source_text",
        "removed_text",
    )
    new_text = _first_nonempty(
        change,
        "new_text",
        "after_text",
        "new_content",
        "target_text",
        "added_text",
    )

    from_chunk = change.get("from_chunk")
    to_chunk = change.get("to_chunk")
    old_chunk = change.get("old_chunk")
    new_chunk = change.get("new_chunk")

    if not old_text and isinstance(from_chunk, dict):
        old_text = _first_nonempty(
            from_chunk,
            "text",
            "content",
            "normalized_text",
            "body",
            "value",
            "extracted_text",
        )

    if not new_text and isinstance(to_chunk, dict):
        new_text = _first_nonempty(
            to_chunk,
            "text",
            "content",
            "normalized_text",
            "body",
            "value",
            "extracted_text",
        )

    if not old_text and isinstance(old_chunk, dict):
        old_text = _first_nonempty(
            old_chunk,
            "text",
            "content",
            "normalized_text",
            "body",
            "value",
            "extracted_text",
        )

    if not new_text and isinstance(new_chunk, dict):
        new_text = _first_nonempty(
            new_chunk,
            "text",
            "content",
            "normalized_text",
            "body",
            "value",
            "extracted_text",
        )

    diff_text = _first_nonempty(
        change,
        "diff_text",
        "diff",
        "difference",
        "patch",
        "summary",
    )

    if not diff_text:
        diff_text = _build_diff_text(old_text, new_text)

    return old_text, new_text, diff_text


def infer_change_type(
    change: Mapping[str, Any], old_text: str, new_text: str, diff_text: str
) -> str:
    type_mapping = {
        "deadline_change": "deadline",
        "document_change": "document",
        "obligation_change": "obligation",
        "service_procedure_change": "procedure",
        "refusal_change": "refusal",
        "editorial_change": "editorial",
        "structural_change": "structure",
    }

    for key in ("semantic_type", "change_type", "category", "kind"):
        raw = _normalize_text(_stringify(change.get(key)))
        if raw in KNOWN_CHANGE_TYPES:
            return raw

    change_classification = change.get("change_classification")
    if isinstance(change_classification, dict):
        primary_type = _normalize_text(
            _stringify(change_classification.get("primary_type"))
        )
        if primary_type in type_mapping:
            return type_mapping[primary_type]

    text = _normalize_text(" ".join([old_text, new_text, diff_text]))

    if re.search(r"\bсрок\b|\bрабоч\w*\s+дн", text):
        return "deadline"

    if re.search(r"основан\w+\s+для\s+отказ|\bотказ\w*", text):
        return "refusal"

    if re.search(r"\bобязан\w*|\bобязател\w*", text):
        return "obligation"

    if re.search(r"\bответственност\w*|\bдисциплинарн\w*|\bматериальн\w*", text):
        return "responsibility"

    if re.search(
        r"\bпредставля\w+\b.*\bдокумент|\bснилс\b|\bпаспорт\b|\bдоверенност\w*",
        text,
    ):
        return "document"

    if re.search(
        r"\bпредварительн\w+\s+запис|\bличн\w+\s+кабинет|\bуведомлен\w*|\bконсультирован\w*",
        text,
    ):
        return "procedure"

    if re.search(r"\bместу\s+пребывания\b|\bзаконн\w+\s+представител\w*", text):
        return "condition"

    if re.search(
        r"\bтелефон\w*|\bгоряч\w+\s+лини|\bофициальн\w+\s+сайт|\bинформационн\w+\s+стенд",
        text,
    ):
        return "informational"

    old_canon = re.sub(r"[^\w\s]", " ", _normalize_text(old_text))
    new_canon = re.sub(r"[^\w\s]", " ", _normalize_text(new_text))
    old_canon = re.sub(r"\s+", " ", old_canon).strip()
    new_canon = re.sub(r"\s+", " ", new_canon).strip()

    if old_canon == new_canon:
        return "editorial"

    return "unclassified"


def _extract_deadline_entities(old_text: str, new_text: str) -> list[dict[str, str]]:
    entities: list[dict[str, str]] = []
    pattern = re.compile(r"(\d+\s+(?:рабочих?|календарных?)\s+дн\w*)", re.IGNORECASE)

    old_match = pattern.search(old_text)
    new_match = pattern.search(new_text)

    if old_match:
        entities.append({"type": "deadline_old", "value": old_match.group(1)})
    if new_match:
        entities.append({"type": "deadline_new", "value": new_match.group(1)})

    return entities


def _extract_document_entities(old_text: str, new_text: str) -> list[dict[str, str]]:
    entities: list[dict[str, str]] = []

    old_match = re.search(r"представля\w+\s+(.+)", old_text, re.IGNORECASE)
    new_match = re.search(r"представля\w+\s+(.+)", new_text, re.IGNORECASE)

    if old_match:
        entities.append(
            {"type": "required_documents_old", "value": old_match.group(1).strip(" .")}
        )
    if new_match:
        entities.append(
            {"type": "required_documents_new", "value": new_match.group(1).strip(" .")}
        )

    return entities


def extract_entities_baseline(
    change_type: str,
    old_text: str,
    new_text: str,
) -> list[dict[str, str]]:
    if change_type == "deadline":
        return _extract_deadline_entities(old_text, new_text)

    if change_type == "document":
        return _extract_document_entities(old_text, new_text)

    if change_type == "refusal":
        return [{"type": "refusal_change", "value": "true"}]

    if change_type == "obligation":
        return [{"type": "staff_action", "value": "обязанность сотрудника"}]

    if change_type == "responsibility":
        return [{"type": "responsibility_change", "value": "true"}]

    if change_type == "procedure":
        return [{"type": "procedure_change", "value": "true"}]

    if change_type == "condition":
        return [{"type": "condition_change", "value": "true"}]

    if change_type == "informational":
        return [{"type": "info_change", "value": "true"}]

    if change_type in {"editorial", "structure"}:
        return [{"type": "editorial_change", "value": "true"}]

    return []


def get_significance_label(change: Mapping[str, Any]) -> str:
    nested_significance = change.get("significance")
    if isinstance(nested_significance, Mapping):
        label = _normalize_text(_stringify(nested_significance.get("label")))
        if label in SIGNIFICANCE_LABELS:
            return label

    nested_importance = change.get("importance")
    if isinstance(nested_importance, Mapping):
        label = _normalize_text(_stringify(nested_importance.get("label")))
        if label in SIGNIFICANCE_LABELS:
            return label

    for key in ("significance_label", "importance_label"):
        label = _normalize_text(_stringify(change.get(key)))
        if label in SIGNIFICANCE_LABELS:
            return label

    return "not_evaluated"


def get_significance_score(change: Mapping[str, Any]) -> float:
    for key in ("significance_score", "importance_confidence"):
        value = change.get(key)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                continue

    nested_significance = change.get("significance")
    if isinstance(nested_significance, Mapping):
        value = nested_significance.get("confidence")
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                pass

    nested_importance = change.get("importance")
    if isinstance(nested_importance, Mapping):
        value = nested_importance.get("confidence")
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                pass

    return 0.0


def get_requires_manual_review(change: Mapping[str, Any]) -> bool:
    raw = change.get("requires_manual_review")
    if raw is not None:
        return bool(raw)

    nested_significance = change.get("significance")
    if isinstance(nested_significance, Mapping):
        raw = nested_significance.get("requires_manual_review")
        if raw is not None:
            return bool(raw)

    nested_importance = change.get("importance")
    if isinstance(nested_importance, Mapping):
        raw = nested_importance.get("requires_manual_review")
        if raw is not None:
            return bool(raw)

    return False


def get_semantic_type(change: Mapping[str, Any]) -> str:
    for key in ("semantic_type", "change_type"):
        value = _normalize_text(_stringify(change.get(key)))
        if value in KNOWN_CHANGE_TYPES:
            return value
    return "unclassified"


def _payload_priority_key(
    change: Mapping[str, Any],
    *,
    original_order: int,
) -> tuple[int, bool, float, int]:
    label = get_significance_label(change)
    score = get_significance_score(change)
    requires_manual_review = get_requires_manual_review(change)
    return (
        -LABEL_PRIORITY.get(label, 0),
        requires_manual_review,
        -score,
        original_order,
    )


def build_materialized_change_item_sort_key(
    change_item: Any,
) -> tuple[int, bool, float, int]:
    label = _normalize_text(getattr(change_item, "significance_label", ""))
    score = getattr(change_item, "significance_score", 0.0) or 0.0
    requires_manual_review = bool(getattr(change_item, "requires_manual_review", False))
    sort_order = getattr(change_item, "sort_order", 0) or 0

    try:
        score_value = float(score)
    except (TypeError, ValueError):
        score_value = 0.0

    return (
        -LABEL_PRIORITY.get(label, 0),
        requires_manual_review,
        -score_value,
        int(sort_order),
    )


def iter_prioritized_change_entries(
    diff_payload: Mapping[str, Any],
) -> list[tuple[str, dict[str, Any]]]:
    from .diff import iter_ordered_change_entries

    entries: list[tuple[str, dict[str, Any]]] = []
    for original_order, (change_operation, payload) in enumerate(
        iter_ordered_change_entries(dict(diff_payload)),
        start=1,
    ):
        enriched = enrich_change(payload)
        enriched["_diff_operation"] = change_operation
        enriched["_original_order"] = original_order
        entries.append((change_operation, enriched))

    entries.sort(
        key=lambda item: _payload_priority_key(
            item[1],
            original_order=int(item[1].get("_original_order", 0) or 0),
        )
    )
    return entries


def select_prioritized_change_entries(
    diff_payload: Mapping[str, Any],
    *,
    limit: int | None = None,
    prefer_non_editorial: bool = False,
) -> list[tuple[str, dict[str, Any]]]:
    entries = iter_prioritized_change_entries(diff_payload)

    if prefer_non_editorial:
        non_editorial_entries = [
            item for item in entries if get_significance_label(item[1]) != "editorial"
        ]
        editorial_entries = [
            item for item in entries if get_significance_label(item[1]) == "editorial"
        ]
        if non_editorial_entries:
            entries = non_editorial_entries + editorial_entries

    if limit is not None:
        return entries[:limit]
    return entries


def select_prioritized_change_items(
    change_items: list[Any],
    *,
    limit: int | None = None,
    prefer_non_editorial: bool = False,
) -> list[Any]:
    entries = sorted(change_items, key=build_materialized_change_item_sort_key)

    if prefer_non_editorial:
        non_editorial_entries = [
            item
            for item in entries
            if _normalize_text(getattr(item, "significance_label", "")) != "editorial"
        ]
        editorial_entries = [
            item
            for item in entries
            if _normalize_text(getattr(item, "significance_label", "")) == "editorial"
        ]
        if non_editorial_entries:
            entries = non_editorial_entries + editorial_entries

    if limit is not None:
        return entries[:limit]
    return entries


def summarize_payload_significance(
    payload: Mapping[str, Any],
) -> tuple[dict[str, int], int]:
    counts = {label: 0 for label in SIGNIFICANCE_LABELS}
    requires_manual_review_count = 0

    for key in ("added", "removed", "modified", "moved"):
        raw_items = payload.get(key, [])
        if not isinstance(raw_items, list):
            continue

        for item in raw_items:
            if not isinstance(item, Mapping):
                continue
            label = get_significance_label(item)
            counts[label] = counts.get(label, 0) + 1
            if get_requires_manual_review(item):
                requires_manual_review_count += 1

    counts = {label: value for label, value in counts.items() if value > 0}
    return counts, requires_manual_review_count


def enrich_change(change: Mapping[str, Any]) -> dict[str, Any]:
    old_text, new_text, diff_text = extract_change_texts(change)

    change_type = _normalize_text(_stringify(change.get("semantic_type")))
    if change_type not in KNOWN_CHANGE_TYPES:
        change_type = _normalize_text(_stringify(change.get("change_type")))
    if change_type not in KNOWN_CHANGE_TYPES:
        change_type = infer_change_type(change, old_text, new_text, diff_text)

    extracted_entities = change.get("extracted_entities")
    if not extracted_entities:
        extracted_entities = extract_entities_baseline(change_type, old_text, new_text)

    prediction = classify_change_importance(
        old_text=old_text,
        new_text=new_text,
        diff_text=diff_text,
        change_type=change_type,
        extracted_entities=extracted_entities,
    )
    prediction_payload = prediction.to_dict()

    enriched = dict(change)
    enriched["old_text"] = old_text
    enriched["new_text"] = new_text
    enriched["diff_text"] = diff_text
    enriched["semantic_type"] = change_type
    enriched["change_type"] = change_type
    enriched["extracted_entities"] = extracted_entities
    enriched["significance"] = prediction_payload
    enriched["significance_label"] = prediction.label
    enriched["significance_score"] = prediction.confidence
    enriched["significance_reason"] = prediction.explanation
    enriched["significance_rules"] = prediction.triggered_rules
    enriched["requires_manual_review"] = prediction.requires_manual_review

    enriched["importance"] = prediction_payload
    enriched["importance_label"] = prediction.label
    enriched["importance_confidence"] = prediction.confidence
    enriched["importance_explanation"] = prediction.explanation
    enriched["importance_triggered_rules"] = prediction.triggered_rules
    return enriched


def enrich_compare_payload(payload: Any) -> Any:
    if isinstance(payload, list):
        return [
            enrich_change(item) if isinstance(item, Mapping) else item
            for item in payload
        ]

    if isinstance(payload, dict):
        result = dict(payload)

        for key in ("changes", "results", "added", "removed", "modified", "moved"):
            if isinstance(result.get(key), list):
                result[key] = [
                    enrich_change(item) if isinstance(item, Mapping) else item
                    for item in result[key]
                ]

        if isinstance(result.get("summary"), dict):
            summary = dict(result["summary"])
            counts, requires_manual_review_count = summarize_payload_significance(
                result
            )
            summary["by_significance"] = counts
            summary["manual_review_count"] = requires_manual_review_count
            result["summary"] = summary

        return result

    return payload
