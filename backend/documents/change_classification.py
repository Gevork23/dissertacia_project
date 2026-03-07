from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

from .change_types import ChangeType
from .entity_extraction import extract_entities_from_text
from .entity_schema import EntityType

DOMAIN_KEYWORDS = {
    ChangeType.DEADLINE.value: (
        "срок",
        "рабочих дней",
        "календарных дней",
        "день обращения",
        "межведомственного запроса",
    ),
    ChangeType.DOCUMENT.value: (
        "документ",
        "документы",
        "заявление",
        "паспорт",
        "согласие на обработку персональных данных",
        "полномочия представителя",
    ),
    ChangeType.OBLIGATION.value: (
        "обязан",
        "обязана",
        "обязаны",
        "должен",
        "должна",
        "проверить",
        "проинформировать",
        "выдать",
        "принять",
    ),
    ChangeType.SERVICE_PROCEDURE.value: (
        "порядок",
        "процедура",
        "прием заявителей",
        "предоставление услуги",
        "выдача результата",
        "информирование",
        "рассмотрение",
    ),
    ChangeType.REFUSAL.value: (
        "отказ",
        "основания отказа",
        "неполного комплекта документов",
        "недостоверных сведений",
        "отсутствия права",
        "полномочия представителя",
    ),
}


TYPE_PRIORITY = [
    ChangeType.STRUCTURAL.value,
    ChangeType.REFUSAL.value,
    ChangeType.DOCUMENT.value,
    ChangeType.DEADLINE.value,
    ChangeType.OBLIGATION.value,
    ChangeType.SERVICE_PROCEDURE.value,
    ChangeType.EDITORIAL.value,
]


def _normalize_spaces(value: str) -> str:
    return " ".join((value or "").strip().split())


def _lexical_similarity(left: str, right: str) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def _normalize_for_editorial_check(text: str) -> str:
    lowered = (text or "").lower()
    lowered = re.sub(r"[^\w\s]+", " ", lowered, flags=re.UNICODE)
    lowered = re.sub(r"\s+", " ", lowered, flags=re.UNICODE)
    return lowered.strip()


def _entity_types_for_text(
    text: str,
    heading: str = "",
    section_path: str = "",
) -> set[str]:
    entities = extract_entities_from_text(
        text,
        heading=heading,
        section_path=section_path,
    )
    return {str(entity["entity_type"]) for entity in entities}


def _boost_scores_by_entities(
    scores: dict[str, float],
    entity_types: set[str],
) -> None:
    if EntityType.DEADLINE.value in entity_types:
        scores[ChangeType.DEADLINE.value] += 4.0
    if EntityType.REQUIRED_DOCUMENT.value in entity_types:
        scores[ChangeType.DOCUMENT.value] += 4.0
    if EntityType.OBLIGATION.value in entity_types:
        scores[ChangeType.OBLIGATION.value] += 4.0
    if EntityType.REFUSAL_REASON.value in entity_types:
        scores[ChangeType.REFUSAL.value] += 4.0
    if EntityType.SERVICE.value in entity_types:
        scores[ChangeType.SERVICE_PROCEDURE.value] += 2.0
    if EntityType.CONDITION.value in entity_types:
        scores[ChangeType.SERVICE_PROCEDURE.value] += 1.0
    if EntityType.AUTHORITY_UNIT.value in entity_types:
        scores[ChangeType.OBLIGATION.value] += 1.0
        scores[ChangeType.SERVICE_PROCEDURE.value] += 1.0


def _boost_scores_by_keywords(
    scores: dict[str, float],
    text: str,
) -> None:
    lowered = (text or "").lower()
    for change_type, keywords in DOMAIN_KEYWORDS.items():
        for keyword in keywords:
            if keyword in lowered:
                scores[change_type] += 1.0


def _make_empty_scores() -> dict[str, float]:
    return {
        ChangeType.DEADLINE.value: 0.0,
        ChangeType.DOCUMENT.value: 0.0,
        ChangeType.OBLIGATION.value: 0.0,
        ChangeType.SERVICE_PROCEDURE.value: 0.0,
        ChangeType.REFUSAL.value: 0.0,
        ChangeType.EDITORIAL.value: 0.0,
        ChangeType.STRUCTURAL.value: 0.0,
    }


def _finalize_classification(
    *,
    scores: dict[str, float],
    rationale: list[str],
) -> dict[str, Any]:
    matched_types = [
        change_type
        for change_type, score in scores.items()
        if score > 0
    ]

    if not matched_types:
        matched_types = [ChangeType.EDITORIAL.value]
        scores[ChangeType.EDITORIAL.value] = 1.0
        rationale.append("Не найдено доменных сигналов, изменение отнесено к editorial.")

    primary_type = sorted(
        matched_types,
        key=lambda item: (
            scores[item],
            -TYPE_PRIORITY.index(item),
        ),
        reverse=True,
    )[0]

    sorted_scores = {
        key: round(value, 3)
        for key, value in sorted(
            scores.items(),
            key=lambda item: (item[1], -TYPE_PRIORITY.index(item[0])),
            reverse=True,
        )
        if value > 0
    }

    return {
        "primary_type": primary_type,
        "matched_types": sorted(
            matched_types,
            key=lambda item: (
                scores[item],
                -TYPE_PRIORITY.index(item),
            ),
            reverse=True,
        ),
        "scores": sorted_scores,
        "rationale": rationale,
    }


def classify_added_or_removed_chunk(
    chunk: dict[str, Any],
    *,
    operation: str,
) -> dict[str, Any]:
    text = chunk.get("text", "")
    heading = chunk.get("heading", "")
    section_path = chunk.get("section_path", "")

    scores = _make_empty_scores()
    rationale: list[str] = [
        f"Операция diff: {operation}.",
    ]

    entity_types = _entity_types_for_text(
        text,
        heading=heading,
        section_path=section_path,
    )
    _boost_scores_by_entities(scores, entity_types)
    _boost_scores_by_keywords(scores, text)
    _boost_scores_by_keywords(scores, heading)

    if entity_types:
        rationale.append(f"Найдены сущности: {sorted(entity_types)}.")

    if scores[ChangeType.DEADLINE.value] > 0:
        rationale.append("Есть признаки изменения сроков.")
    if scores[ChangeType.DOCUMENT.value] > 0:
        rationale.append("Есть признаки изменения перечня документов.")
    if scores[ChangeType.OBLIGATION.value] > 0:
        rationale.append("Есть признаки изменения обязанностей.")
    if scores[ChangeType.REFUSAL.value] > 0:
        rationale.append("Есть признаки изменения оснований отказа.")
    if scores[ChangeType.SERVICE_PROCEDURE.value] > 0:
        rationale.append("Есть признаки изменения порядка оказания услуги.")

    return _finalize_classification(scores=scores, rationale=rationale)


def classify_moved_chunk_pair(
    from_chunk: dict[str, Any],
    to_chunk: dict[str, Any],
) -> dict[str, Any]:
    scores = _make_empty_scores()
    rationale = [
        "Фрагмент перемещён без исчезновения из документа.",
        "Изменение отнесено к structural_change.",
    ]
    scores[ChangeType.STRUCTURAL.value] = 10.0

    if from_chunk.get("section_path") != to_chunk.get("section_path"):
        rationale.append("Изменился section_path.")
    if from_chunk.get("heading") != to_chunk.get("heading"):
        rationale.append("Изменился heading.")
    if from_chunk.get("chunk_index") != to_chunk.get("chunk_index"):
        rationale.append("Изменился chunk_index.")

    return _finalize_classification(scores=scores, rationale=rationale)


def classify_modified_chunk_pair(
    from_chunk: dict[str, Any],
    to_chunk: dict[str, Any],
    *,
    similarity: float,
    match_reason: str,
) -> dict[str, Any]:
    from_text = from_chunk.get("text", "")
    to_text = to_chunk.get("text", "")
    from_heading = from_chunk.get("heading", "")
    to_heading = to_chunk.get("heading", "")
    from_section = from_chunk.get("section_path", "")
    to_section = to_chunk.get("section_path", "")

    scores = _make_empty_scores()
    rationale = [
        "Операция diff: modified.",
        f"Similarity={round(similarity, 4)}.",
        f"Match reason={match_reason}.",
    ]

    old_entity_types = _entity_types_for_text(
        from_text,
        heading=from_heading,
        section_path=from_section,
    )
    new_entity_types = _entity_types_for_text(
        to_text,
        heading=to_heading,
        section_path=to_section,
    )

    all_entity_types = old_entity_types | new_entity_types

    _boost_scores_by_entities(scores, all_entity_types)
    _boost_scores_by_keywords(scores, from_text)
    _boost_scores_by_keywords(scores, to_text)
    _boost_scores_by_keywords(scores, from_heading)
    _boost_scores_by_keywords(scores, to_heading)

    if old_entity_types or new_entity_types:
        rationale.append(
            f"Сущности до/после: old={sorted(old_entity_types)} "
            f"new={sorted(new_entity_types)}."
        )

    from_editorial = _normalize_for_editorial_check(from_text)
    to_editorial = _normalize_for_editorial_check(to_text)

    same_entity_profile = old_entity_types == new_entity_types
    close_lexically = _lexical_similarity(from_editorial, to_editorial) >= 0.95

    if same_entity_profile and close_lexically:
        scores[ChangeType.EDITORIAL.value] += 5.0
        rationale.append(
            "Текст близок лексически и профиль сущностей не изменился: "
            "похоже на редакционное изменение."
        )

    editorial_vocab = (
        "текст",
        "материал",
        "информацион",
        "ясно",
        "последовательно",
        "изложен",
    )
    editorial_context = (
        any(token in from_editorial for token in editorial_vocab)
        or any(token in to_editorial for token in editorial_vocab)
    )

    only_soft_domain_signal = all_entity_types <= {
        EntityType.OBLIGATION.value,
        EntityType.SERVICE.value,
        EntityType.CONDITION.value,
    }

    if similarity >= 0.95 and editorial_context and only_soft_domain_signal:
        scores[ChangeType.EDITORIAL.value] += 6.0
        scores[ChangeType.OBLIGATION.value] = max(
            0.0,
            scores[ChangeType.OBLIGATION.value] - 3.0,
        )
        rationale.append(
            "Контекст выглядит редакционным, а доменные сигналы слабые: "
            "приоритет смещён к editorial_change."
        )

    if (
        match_reason in {"section_path", "heading"}
        and similarity >= 0.95
        and from_text == to_text
    ):
        scores[ChangeType.STRUCTURAL.value] += 8.0
        rationale.append(
            "Текст совпадает, но изменена структура расположения фрагмента."
        )

    if (
        not any(
            scores[item] > 0
            for item in (
                ChangeType.DEADLINE.value,
                ChangeType.DOCUMENT.value,
                ChangeType.OBLIGATION.value,
                ChangeType.SERVICE_PROCEDURE.value,
                ChangeType.REFUSAL.value,
            )
        )
        and similarity >= 0.92
    ):
        scores[ChangeType.EDITORIAL.value] += 3.0
        rationale.append(
            "Нет сильных доменных сигналов, изменение похоже на редакционное."
        )

    return _finalize_classification(scores=scores, rationale=rationale)

def summarize_change_types(diff_payload: dict[str, Any]) -> dict[str, int]:
    counts = {
        ChangeType.DEADLINE.value: 0,
        ChangeType.DOCUMENT.value: 0,
        ChangeType.OBLIGATION.value: 0,
        ChangeType.SERVICE_PROCEDURE.value: 0,
        ChangeType.REFUSAL.value: 0,
        ChangeType.EDITORIAL.value: 0,
        ChangeType.STRUCTURAL.value: 0,
    }

    groups = (
        diff_payload.get("added", []),
        diff_payload.get("removed", []),
        diff_payload.get("modified", []),
        diff_payload.get("moved", []),
    )

    for group in groups:
        for item in group:
            change_classification = item.get("change_classification") or {}
            primary_type = change_classification.get("primary_type")
            if primary_type in counts:
                counts[primary_type] += 1

    return counts