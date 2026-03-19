from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Mapping

LABELS = ("critical", "important", "informational", "editorial")
LABEL_PRIORITY = {
    "critical": 4,
    "important": 3,
    "informational": 2,
    "editorial": 1,
}

CRITICAL_CHANGE_TYPES = {
    "deadline",
    "document",
    "refusal",
    "obligation",
    "responsibility",
}

IMPORTANT_CHANGE_TYPES = {
    "procedure",
    "condition",
}

INFORMATIONAL_CHANGE_TYPES = {
    "informational",
}

EDITORIAL_CHANGE_TYPES = {
    "editorial",
    "structure",
}

CRITICAL_ENTITY_TYPES = {
    "deadline_old",
    "deadline_new",
    "required_documents_old",
    "required_documents_new",
    "refusal_change",
    "staff_action",
    "responsibility_change",
}

IMPORTANT_ENTITY_TYPES = {
    "procedure_change",
    "condition_change",
}

INFORMATIONAL_ENTITY_TYPES = {
    "info_change",
}

EDITORIAL_ENTITY_TYPES = {
    "editorial_change",
    "structure_change",
}

CRITICAL_PATTERNS = (
    r"\bсрок\b",
    r"рабоч\w*\s+дн",
    r"основан\w+\s+для\s+отказ",
    r"\bотказ\w*",
    r"\bобязан\w*",
    r"\bобязател\w*",
    r"\bдисциплинарн\w*",
    r"\bматериальн\w*",
    r"\bответственност\w*",
    r"\bснилс\b",
    r"\bдоверенност\w*",
)

IMPORTANT_PATTERNS = (
    r"\bпредварительн\w+\s+запис",
    r"\bличн\w+\s+кабинет",
    r"\bпредставител\w*",
    r"\bуведомлен\w*",
    r"\bконсультирован\w*",
    r"\bокн\w+\s+обслуживан",
    r"\bместу\s+пребывания\b",
    r"\bвыдаетс[яь]\b",
    r"\bпроверка\s+заявлен",
    r"\bпрофильн\w+\s+отдел",
)

INFORMATIONAL_PATTERNS = (
    r"\bтелефон\w*",
    r"\bгоряч\w+\s+лини",
    r"\bофициальн\w+\s+сайт",
    r"\bинформационн\w+\s+стенд",
    r"\bпример\w*\s+заполнен",
    r"\bсправочн\w+\s+номер",
    r"\bпояснен\w*",
    r"8-800",
)


@dataclass
class ImportancePrediction:
    label: str
    confidence: float
    triggered_rules: list[str]
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalize_text(text: str | None) -> str:
    text = (text or "").lower().replace("ё", "е")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _canonical_editorial(text: str | None) -> str:
    text = _normalize_text(text)
    text = re.sub(r"[\"'`«»“”„’.,;:!?()\[\]{}\-—–_/\\№]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _parse_entities(extracted_entities: Any) -> list[dict[str, Any]]:
    if extracted_entities in (None, "", [], ()):
        return []

    if isinstance(extracted_entities, str):
        try:
            data = json.loads(extracted_entities)
        except json.JSONDecodeError:
            return []
    elif isinstance(extracted_entities, list):
        data = extracted_entities
    else:
        return []

    return [item for item in data if isinstance(item, dict)]


def _entity_types(entities: list[dict[str, Any]]) -> set[str]:
    result: set[str] = set()
    for item in entities:
        value = item.get("type")
        if value is not None:
            result.add(_normalize_text(str(value)))
    return result


def _matches_any(patterns: tuple[str, ...], text: str) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)


def _looks_like_contact_or_reference_addition(old_text: str, new_text: str) -> bool:
    old_norm = _normalize_text(old_text)
    new_norm = _normalize_text(new_text)
    if len(new_norm) <= len(old_norm):
        return False

    had_info_before = _matches_any(INFORMATIONAL_PATTERNS, old_norm)
    has_info_now = _matches_any(INFORMATIONAL_PATTERNS, new_norm)
    return has_info_now and not had_info_before


def _build_explanation(label: str, triggered_rules: list[str]) -> str:
    explanations = {
        "critical": "Изменение затрагивает ключевые условия оказания услуги или обязанности/основания отказа.",
        "important": "Изменение влияет на порядок работы или условия взаимодействия, но не является самым критичным.",
        "informational": "Изменение в основном добавляет справочную или поясняющую информацию.",
        "editorial": "Изменение похоже на редакционное или структурное и не меняет смысл по существу.",
    }

    if triggered_rules:
        return f"{explanations[label]} Сработали правила: {', '.join(triggered_rules)}."

    return explanations[label]


def classify_change_importance(
    *,
    old_text: str = "",
    new_text: str = "",
    diff_text: str = "",
    change_type: str | None = None,
    extracted_entities: Any = None,
) -> ImportancePrediction:
    if not diff_text:
        diff_text = f"OLD: {old_text}\nNEW: {new_text}"

    old_norm = _normalize_text(old_text)
    new_norm = _normalize_text(new_text)
    combined_text = _normalize_text(
        " ".join(part for part in (old_text, new_text, diff_text) if part)
    )
    change_type_norm = _normalize_text(change_type)
    entities = _parse_entities(extracted_entities)
    entity_types = _entity_types(entities)

    scores = {label: 0 for label in LABELS}
    reasons = {label: [] for label in LABELS}

    def hit(label: str, score: int, reason: str) -> None:
        if score > scores[label]:
            scores[label] = score
        if reason not in reasons[label]:
            reasons[label].append(reason)

    # 1. Явные сигналы по типу изменения
    if change_type_norm in CRITICAL_CHANGE_TYPES:
        hit("critical", 100, f"change_type={change_type_norm}")

    if change_type_norm in IMPORTANT_CHANGE_TYPES:
        hit("important", 100, f"change_type={change_type_norm}")

    if change_type_norm in INFORMATIONAL_CHANGE_TYPES:
        hit("informational", 100, f"change_type={change_type_norm}")

    if change_type_norm in EDITORIAL_CHANGE_TYPES:
        hit("editorial", 100, f"change_type={change_type_norm}")

    # 2. Сигналы по извлечённым сущностям
    critical_entities = entity_types & CRITICAL_ENTITY_TYPES
    important_entities = entity_types & IMPORTANT_ENTITY_TYPES
    informational_entities = entity_types & INFORMATIONAL_ENTITY_TYPES
    editorial_entities = entity_types & EDITORIAL_ENTITY_TYPES

    if critical_entities:
        hit("critical", 95, f"entities={','.join(sorted(critical_entities))}")

    if important_entities:
        hit("important", 95, f"entities={','.join(sorted(important_entities))}")

    if informational_entities:
        hit("informational", 95, f"entities={','.join(sorted(informational_entities))}")

    if editorial_entities:
        hit("editorial", 95, f"entities={','.join(sorted(editorial_entities))}")

    # 3. Сигналы по тексту
    if _matches_any(CRITICAL_PATTERNS, combined_text):
        hit("critical", 90, "critical_keywords")

    if _matches_any(IMPORTANT_PATTERNS, combined_text):
        hit("important", 90, "important_keywords")

    if _matches_any(INFORMATIONAL_PATTERNS, combined_text):
        hit("informational", 90, "informational_keywords")

    # 4. Редакционные эвристики
    if (
        old_norm
        and new_norm
        and _canonical_editorial(old_text) == _canonical_editorial(new_text)
    ):
        hit("editorial", 85, "normalized_text_equal")

    if _looks_like_contact_or_reference_addition(old_text, new_text):
        hit("informational", 80, "contact_or_reference_added")

    # 5. Fallback
    if not any(scores.values()):
        hit("important", 51, "fallback_manual_review")

    # При одинаковом score приоритет: critical > important > informational > editorial
    best_label = max(LABELS, key=lambda label: (scores[label], LABEL_PRIORITY[label]))
    best_rules = reasons[best_label] or ["fallback_manual_review"]
    confidence = round(scores[best_label] / 100, 2)
    explanation = _build_explanation(best_label, best_rules)

    return ImportancePrediction(
        label=best_label,
        confidence=confidence,
        triggered_rules=best_rules,
        explanation=explanation,
    )


def classify_change_row(row: Mapping[str, Any]) -> ImportancePrediction:
    return classify_change_importance(
        old_text=str(row.get("old_text", "")),
        new_text=str(row.get("new_text", "")),
        diff_text=str(row.get("diff_text", "")),
        change_type=str(row.get("change_type", "")),
        extracted_entities=row.get("extracted_entities"),
    )
