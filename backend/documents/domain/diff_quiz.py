from __future__ import annotations

from typing import Any, Iterable

from .change_enrichment import get_significance_label
from .diff_summary import build_brief_summary

QUIZ_PRIMARY_LABELS = {"critical", "important", "informational", "not_evaluated"}
NON_QUIZ_SEMANTIC_TYPES = {"editorial", "structure"}
MAX_QUESTIONS_PER_SEMANTIC_TYPE = 2

GENERIC_DISTRACTORS = {
    "added": [
        "Изменений в этом разделе не обнаружено.",
        "Фрагмент был исключён, а не добавлен.",
        "Правка носит только редакционный характер и не меняет требования.",
    ],
    "removed": [
        "Фрагмент был добавлен в новой редакции.",
        "Содержание раздела осталось без изменений.",
        "Изменение касается только уточнения формулировки без исключения требования.",
    ],
    "modified": [
        "Содержание нормы не изменилось, была только редакционная правка.",
        "Фрагмент был только перемещён внутри документа.",
        "Изменение относится к другому разделу и не влияет на эту норму.",
    ],
    "moved": [
        "Фрагмент исключён без переноса.",
        "Фрагмент добавлен заново и ранее отсутствовал.",
        "Изменение касается только текста нормы, а не её положения в документе.",
    ],
}

SEMANTIC_DISTRACTORS = {
    "deadline": [
        "Сроки выполнения требований не изменились.",
        "Изменение касается только перечня документов, а не сроков.",
        "Правка относится только к оформлению текста без изменения срока.",
    ],
    "document": [
        "Перечень документов остался прежним.",
        "Изменение касается только сроков предоставления услуги.",
        "Правка относится только к редакционному оформлению документа.",
    ],
    "obligation": [
        "Обязанности сотрудников и заявителей не изменились.",
        "Изменение касается только справочной информации.",
        "Правка затронула только нумерацию раздела.",
    ],
    "procedure": [
        "Порядок действий и последовательность процедуры остались прежними.",
        "Изменение касается только перечня документов.",
        "В разделе исправлена только редакционная формулировка.",
    ],
    "refusal": [
        "Основания для отказа остались без изменений.",
        "Изменение касается только сроков оказания услуги.",
        "В разделе изменена только структура без нового основания отказа.",
    ],
    "condition": [
        "Условия предоставления услуги не менялись.",
        "Изменение относится только к срокам рассмотрения заявления.",
        "Правка является редакционной и не меняет условия применения нормы.",
    ],
    "responsibility": [
        "Положения об ответственности не изменились.",
        "Изменение относится только к справочной части документа.",
        "В разделе изменена только последовательность пунктов.",
    ],
    "informational": [
        "Изменение не влияет на действия сотрудника и носит только справочный характер.",
        "Изменение касается сроков, а не справочной информации.",
        "Перечень обязательных документов остался без изменений.",
    ],
    "unclassified": [
        "Содержательных изменений в этом фрагменте не обнаружено.",
        "Изменение относится к другому разделу документа.",
        "Правка носит только редакционный характер.",
    ],
}

PROMPT_TEMPLATES = {
    "deadline": "Какое изменение по срокам должен учитывать сотрудник в разделе «{title}»?",
    "document": "Какое изменение в перечне документов нужно учитывать в разделе «{title}»?",
    "obligation": "Какое изменение в обязанностях отражено в разделе «{title}»?",
    "procedure": "Как изменился порядок действий в разделе «{title}»?",
    "refusal": "Какое изменение в основаниях отказа отражено в разделе «{title}»?",
    "condition": "Какое изменение условий применения нормы отражено в разделе «{title}»?",
    "responsibility": "Какое изменение в положениях об ответственности отражено в разделе «{title}»?",
    "informational": "Какая новая справочная информация важна в разделе «{title}»?",
    "unclassified": "Какое значимое изменение отражено в разделе «{title}»?",
}


def truncate_text(text: str, max_len: int = 180) -> str:
    normalized = " ".join((text or "").split())
    if len(normalized) <= max_len:
        return normalized
    return f"{normalized[: max_len - 1].rstrip()}…"


def build_chunk_title(chunk: dict[str, Any]) -> str:
    heading = (chunk.get("heading") or "").strip()
    section_path = (chunk.get("section_path") or "").strip()

    if heading:
        return heading
    if section_path:
        return section_path
    return "Фрагмент без заголовка"


def _normalize_option(value: str) -> str:
    return " ".join((value or "").split())


def _normalize_key(value: str | None) -> str:
    return _normalize_option((value or "").lower().replace("ё", "е"))


def _normalize_semantic_type(value: Any) -> str:
    semantic_type = _normalize_key(str(value or ""))
    return semantic_type or "unclassified"


def _infer_selection_scope(highlights: list[dict[str, Any]]) -> str:
    if not highlights:
        return "empty"
    if any(
        _normalize_semantic_type(item.get("semantic_type"))
        not in NON_QUIZ_SEMANTIC_TYPES
        and _normalize_key(item.get("significance_label")) in QUIZ_PRIMARY_LABELS
        for item in highlights
    ):
        return "significant"
    return "editorial_fallback"


def _highlight_signature(item: dict[str, Any]) -> tuple[str, str, str]:
    return (
        _normalize_semantic_type(item.get("semantic_type")),
        _normalize_key(item.get("title")),
        _normalize_key(item.get("concise_explanation") or item.get("description")),
    )


def _question_title(item: dict[str, Any]) -> str:
    title = truncate_text(str(item.get("title") or ""), max_len=120)
    return title or "Фрагмент без заголовка"


def _is_quiz_candidate(item: dict[str, Any]) -> bool:
    semantic_type = _normalize_semantic_type(item.get("semantic_type"))
    significance_label = _normalize_key(item.get("significance_label"))
    if semantic_type in NON_QUIZ_SEMANTIC_TYPES:
        return False
    return significance_label in QUIZ_PRIMARY_LABELS


def _target_text_for_highlight(item: dict[str, Any]) -> str:
    if item.get("type") == "removed":
        return str(item.get("old_text") or "")
    return str(item.get("new_text") or item.get("old_text") or "")


def _looks_structurally_meaningful_fallback(item: dict[str, Any]) -> bool:
    question_type = _normalize_key(item.get("type"))
    if question_type == "moved":
        return False

    target_text = _normalize_key(_target_text_for_highlight(item))
    if len(target_text) < 20:
        return False

    if question_type in {"added", "removed"}:
        return True

    old_text = _normalize_key(item.get("old_text"))
    new_text = _normalize_key(item.get("new_text"))
    if not old_text or not new_text or old_text == new_text:
        return False

    try:
        similarity = float(item.get("similarity"))
    except (TypeError, ValueError):
        similarity = None

    if similarity is not None and similarity >= 0.96:
        return False
    return True


def _fallback_answer_from_highlight(item: dict[str, Any]) -> str:
    question_type = _normalize_key(item.get("type"))
    title = _question_title(item)
    target_text = truncate_text(_target_text_for_highlight(item), max_len=180)

    if question_type == "added" and target_text:
        return f"В разделе «{title}» добавлено новое положение: {target_text}."
    if question_type == "removed" and target_text:
        return f"Из раздела «{title}» исключено положение: {target_text}."
    if question_type == "modified" and target_text:
        return f"В разделе «{title}» обновлена формулировка: {target_text}."
    return target_text


def _select_quiz_highlights(
    highlights: list[dict[str, Any]],
    *,
    max_questions: int,
) -> tuple[list[dict[str, Any]], str]:
    if max_questions <= 0:
        return [], "empty"

    candidates = [item for item in highlights if _is_quiz_candidate(item)]
    selection_scope = "significant"
    if not candidates:
        candidates = [
            item for item in highlights if _looks_structurally_meaningful_fallback(item)
        ]
        selection_scope = "fallback_substantive_editorial"

    if not candidates:
        return [], "empty"

    unique_candidates: list[dict[str, Any]] = []
    seen_signatures: set[tuple[str, str, str]] = set()
    for item in candidates:
        signature = _highlight_signature(item)
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        unique_candidates.append(item)

    selected: list[dict[str, Any]] = []
    semantic_counts: dict[str, int] = {}

    for item in unique_candidates:
        semantic_type = _normalize_semantic_type(item.get("semantic_type"))
        if semantic_counts.get(semantic_type, 0) >= 1:
            continue
        selected.append(item)
        semantic_counts[semantic_type] = semantic_counts.get(semantic_type, 0) + 1
        if len(selected) == max_questions:
            return selected, selection_scope

    for item in unique_candidates:
        if item in selected:
            continue
        semantic_type = _normalize_semantic_type(item.get("semantic_type"))
        if semantic_counts.get(semantic_type, 0) >= MAX_QUESTIONS_PER_SEMANTIC_TYPE:
            continue
        selected.append(item)
        semantic_counts[semantic_type] = semantic_counts.get(semantic_type, 0) + 1
        if len(selected) == max_questions:
            return selected, selection_scope

    return selected, selection_scope


def _build_question_prompt(highlight: dict[str, Any]) -> str:
    semantic_type = _normalize_semantic_type(highlight.get("semantic_type"))
    title = _question_title(highlight)
    template = PROMPT_TEMPLATES.get(semantic_type, PROMPT_TEMPLATES["unclassified"])
    return template.format(title=title)


def _build_question_explanation(highlight: dict[str, Any]) -> str:
    concise_explanation = truncate_text(
        str(highlight.get("concise_explanation") or highlight.get("description") or ""),
        max_len=220,
    )
    significance_reason = truncate_text(
        str(highlight.get("significance_reason") or ""),
        max_len=220,
    )

    parts: list[str] = []
    if concise_explanation:
        parts.append(f"Проверяет понимание изменения: {concise_explanation}")
    if significance_reason:
        parts.append(f"Причина значимости: {significance_reason}")
    return " ".join(parts).strip()


def _semantic_distractor_pool(semantic_type: str, question_type: str) -> list[str]:
    return [
        *SEMANTIC_DISTRACTORS.get(semantic_type, []),
        *GENERIC_DISTRACTORS.get(question_type, []),
    ]


def _build_choices(
    *,
    question_type: str,
    correct_answer: str,
    answer_pool: Iterable[str],
    position_seed: int,
    semantic_type: str,
) -> list[dict[str, Any]]:
    distractors: list[str] = []
    seen = {_normalize_option(correct_answer)}

    for candidate in answer_pool:
        normalized = _normalize_option(candidate)
        if not normalized or normalized in seen:
            continue
        distractors.append(candidate)
        seen.add(normalized)
        if len(distractors) == 2:
            break

    for candidate in _semantic_distractor_pool(semantic_type, question_type):
        normalized = _normalize_option(candidate)
        if not normalized or normalized in seen:
            continue
        distractors.append(candidate)
        seen.add(normalized)
        if len(distractors) == 2:
            break

    if not distractors:
        distractors.append("Содержательных изменений по этому вопросу не было.")
    if len(distractors) == 1:
        distractors.append(
            "Изменение относится к другому содержательному блоку документа."
        )

    options = [correct_answer, *distractors[:2]]
    rotation = position_seed % len(options)
    rotated = options[rotation:] + options[:rotation]

    return [
        {
            "choice_index": index,
            "text": option,
            "is_correct": option == correct_answer,
        }
        for index, option in enumerate(rotated)
    ]


def _question_from_highlight(
    highlight: dict[str, Any],
    *,
    highlight_index: int,
) -> dict[str, Any]:
    answer = truncate_text(
        str(highlight.get("concise_explanation") or highlight.get("description") or ""),
        max_len=220,
    )
    if _normalize_key(
        highlight.get("significance_label")
    ) == "editorial" and _looks_structurally_meaningful_fallback(highlight):
        fallback_answer = _fallback_answer_from_highlight(highlight)
        if fallback_answer:
            answer = truncate_text(fallback_answer, max_len=220)
    semantic_type = _normalize_semantic_type(highlight.get("semantic_type"))
    significance_label = _normalize_key(highlight.get("significance_label"))

    question = {
        "type": str(highlight.get("type") or "modified"),
        "question_type": "single_choice",
        "question": _build_question_prompt(highlight),
        "answer": answer,
        "explanation": _build_question_explanation(highlight),
        "semantic_type": semantic_type,
        "significance_label": significance_label or get_significance_label(highlight),
        "significance_reason": str(highlight.get("significance_reason") or ""),
        "requires_manual_review": bool(highlight.get("requires_manual_review")),
        "source": {
            "title": _question_title(highlight),
            "semantic_type": semantic_type,
            "significance_label": significance_label
            or get_significance_label(highlight),
            "source_change_item_id": highlight.get("source_change_item_id"),
            "source_sort_order": highlight.get("source_sort_order"),
            "source_highlight_index": highlight_index,
        },
        "source_change_item_id": highlight.get("source_change_item_id"),
        "source_sort_order": highlight.get("source_sort_order"),
        "source_highlight_index": highlight_index,
        "summary_title": _question_title(highlight),
        "summary_concise_explanation": answer,
    }

    old_text = highlight.get("old_text")
    new_text = highlight.get("new_text")
    if old_text:
        question["source"]["old_text"] = truncate_text(str(old_text), max_len=140)
    if new_text:
        question["source"]["new_text"] = truncate_text(str(new_text), max_len=140)
    if highlight.get("similarity") is not None:
        question["source"]["similarity"] = highlight.get("similarity")
    if highlight.get("match_reason"):
        question["source"]["match_reason"] = highlight.get("match_reason")

    return question


def _question_payload_from_summary(
    *,
    from_version: dict[str, Any],
    to_version: dict[str, Any],
    identical: bool,
    highlights: list[dict[str, Any]],
    selection_scope: str,
    max_questions: int,
) -> dict[str, Any]:
    selected_highlights, generation_scope = _select_quiz_highlights(
        highlights,
        max_questions=max_questions,
    )
    questions = [
        _question_from_highlight(item, highlight_index=index)
        for index, item in enumerate(selected_highlights)
    ]

    answer_pool = [
        question["answer"] for question in questions if question.get("answer")
    ]
    for index, question in enumerate(questions):
        question["choices"] = _build_choices(
            question_type=question["type"],
            correct_answer=question["answer"],
            answer_pool=answer_pool,
            position_seed=index,
            semantic_type=_normalize_semantic_type(question.get("semantic_type")),
        )

    return {
        "from_version": from_version,
        "to_version": to_version,
        "identical": identical,
        "selection_scope": generation_scope or selection_scope,
        "generation_strategy": "summary_highlights_v1",
        "source_highlights_count": len(highlights),
        "questions_count": len(questions),
        "questions": questions,
    }


def build_quiz_from_summary(
    *,
    summary_payload: dict[str, Any],
    from_version: dict[str, Any],
    to_version: dict[str, Any],
    identical: bool = False,
    max_questions: int = 10,
) -> dict[str, Any]:
    highlights = list(summary_payload.get("highlights") or [])
    selection_scope = str(summary_payload.get("selection_scope") or "").strip()
    if not selection_scope:
        selection_scope = _infer_selection_scope(highlights)

    return _question_payload_from_summary(
        from_version=from_version,
        to_version=to_version,
        identical=identical,
        highlights=highlights,
        selection_scope=selection_scope,
        max_questions=max_questions,
    )


def build_quiz_from_diff(
    diff_payload: dict[str, Any],
    max_questions: int = 10,
) -> dict[str, Any]:
    brief_payload = build_brief_summary(
        diff_payload,
        limit=max(max_questions * 2, max_questions),
    )
    return build_quiz_from_summary(
        summary_payload=brief_payload,
        from_version=diff_payload["from_version"],
        to_version=diff_payload["to_version"],
        identical=bool(diff_payload.get("identical", False)),
        max_questions=max_questions,
    )
