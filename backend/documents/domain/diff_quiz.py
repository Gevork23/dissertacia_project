from __future__ import annotations

from typing import Any

GENERIC_DISTRACTORS = {
    "added": [
        "Изменений в этом разделе не обнаружено.",
        "Фрагмент был удалён, а не добавлен.",
        "Изменение касается только редакционной правки без нового требования.",
    ],
    "removed": [
        "Фрагмент был добавлен в новой редакции.",
        "Содержание раздела осталось без изменений.",
        "Изменение касается только срока оказания услуги.",
    ],
    "modified": [
        "Фрагмент не менялся, а только был перемещён внутри документа.",
        "Изменение касается только названия раздела без смены содержания.",
        "В новой редакции раздел исключён полностью.",
    ],
    "moved": [
        "Фрагмент был удалён без переноса.",
        "Фрагмент был добавлен заново и ранее отсутствовал.",
        "Изменение затронуло только формулировку без смены позиции.",
    ],
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


def build_added_question(chunk: dict[str, Any]) -> dict[str, Any]:
    title = build_chunk_title(chunk)
    text = truncate_text(chunk.get("text", ""))

    return {
        "type": "added",
        "question": f"Что нового добавлено в разделе «{title}»?",
        "answer": text,
        "source": {
            "heading": chunk.get("heading"),
            "section_path": chunk.get("section_path"),
            "chunk_index": chunk.get("chunk_index"),
        },
    }


def build_removed_question(chunk: dict[str, Any]) -> dict[str, Any]:
    title = build_chunk_title(chunk)
    text = truncate_text(chunk.get("text", ""))

    return {
        "type": "removed",
        "question": f"Какой фрагмент был удалён из раздела «{title}»?",
        "answer": text,
        "source": {
            "heading": chunk.get("heading"),
            "section_path": chunk.get("section_path"),
            "chunk_index": chunk.get("chunk_index"),
        },
    }


def build_modified_question(item: dict[str, Any]) -> dict[str, Any]:
    old_chunk = item["from_chunk"]
    new_chunk = item["to_chunk"]
    title = build_chunk_title(new_chunk)

    old_text = truncate_text(old_chunk.get("text", ""), 120)
    new_text = truncate_text(new_chunk.get("text", ""), 120)

    return {
        "type": "modified",
        "question": f"Что изменилось в разделе «{title}»?",
        "answer": f"Было: {old_text} | Стало: {new_text}",
        "source": {
            "heading": new_chunk.get("heading"),
            "section_path": new_chunk.get("section_path"),
            "chunk_index": new_chunk.get("chunk_index"),
            "similarity": item.get("similarity"),
            "match_reason": item.get("match_reason"),
        },
    }


def build_moved_question(item: dict[str, Any]) -> dict[str, Any]:
    from_chunk = item["from_chunk"]
    to_chunk = item["to_chunk"]
    title = build_chunk_title(to_chunk)

    return {
        "type": "moved",
        "question": f"Как был перемещён раздел «{title}»?",
        "answer": (
            f"Фрагмент был перемещён с позиции "
            f"{from_chunk.get('chunk_index')} на позицию {to_chunk.get('chunk_index')}."
        ),
        "source": {
            "heading": to_chunk.get("heading"),
            "section_path": to_chunk.get("section_path"),
            "from_chunk_index": from_chunk.get("chunk_index"),
            "to_chunk_index": to_chunk.get("chunk_index"),
        },
    }


def _normalize_option(value: str) -> str:
    return " ".join((value or "").split())


def _build_choices(
    *,
    question_type: str,
    correct_answer: str,
    answer_pool: list[str],
    position_seed: int,
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

    for candidate in GENERIC_DISTRACTORS.get(question_type, []):
        normalized = _normalize_option(candidate)
        if normalized in seen:
            continue
        distractors.append(candidate)
        seen.add(normalized)
        if len(distractors) == 2:
            break

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


def build_quiz_from_diff(
    diff_payload: dict[str, Any],
    max_questions: int = 10,
) -> dict[str, Any]:
    questions: list[dict[str, Any]] = []

    for chunk in diff_payload["added"]:
        questions.append(build_added_question(chunk))

    for item in diff_payload["modified"]:
        questions.append(build_modified_question(item))

    for chunk in diff_payload["removed"]:
        questions.append(build_removed_question(chunk))

    for item in diff_payload["moved"]:
        questions.append(build_moved_question(item))

    questions = questions[:max_questions]
    answer_pool = [
        question["answer"] for question in questions if question.get("answer")
    ]

    for index, question in enumerate(questions):
        question["question_type"] = "single_choice"
        question["choices"] = _build_choices(
            question_type=question["type"],
            correct_answer=question["answer"],
            answer_pool=answer_pool,
            position_seed=index,
        )

    return {
        "from_version": diff_payload["from_version"],
        "to_version": diff_payload["to_version"],
        "identical": diff_payload["identical"],
        "questions_count": len(questions),
        "questions": questions,
    }
