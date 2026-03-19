from __future__ import annotations

import json
import re
from typing import Any, Mapping

from ..services.importance import classify_change_importance

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
}


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

    for key in ("change_type", "semantic_type", "category", "kind"):
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
        r"\bпредставля\w+\b.*\bдокумент|\bснилс\b|\bпаспорт\b|\bдоверенност\w*", text
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

    return "editorial"


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
    change_type: str, old_text: str, new_text: str
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


def enrich_change(change: Mapping[str, Any]) -> dict[str, Any]:
    old_text, new_text, diff_text = extract_change_texts(change)

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

    enriched = dict(change)
    enriched["old_text"] = old_text
    enriched["new_text"] = new_text
    enriched["diff_text"] = diff_text
    enriched["change_type"] = change_type
    enriched["extracted_entities"] = extracted_entities
    enriched["importance"] = prediction.to_dict()
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

        return result

    return payload
