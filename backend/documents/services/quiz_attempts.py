from __future__ import annotations

from typing import Any


def normalize_text(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def _resolve_submitted_answer(
    question: dict[str, Any], submitted_item: dict[str, Any]
) -> str:
    question_type = question.get("question_type") or question.get("type")

    if question_type == "single_choice":
        choice_index = submitted_item.get("selected_choice_index")
        if choice_index is not None:
            try:
                index = int(choice_index)
            except (TypeError, ValueError):
                index = None
            if index is not None:
                for choice in question.get("choices", []):
                    if choice.get("choice_index") == index:
                        return str(choice.get("text", ""))

        if submitted_item.get("selected_choice_text"):
            return str(submitted_item.get("selected_choice_text"))

    return str(submitted_item.get("answer", ""))


def evaluate_quiz_answers(quiz_payload: dict, submitted_answers: list[dict]) -> dict:
    questions = quiz_payload.get("questions", [])
    submitted_by_index = {}

    for item in submitted_answers:
        try:
            question_index = int(item.get("question_index"))
        except (TypeError, ValueError):
            continue
        submitted_by_index[question_index] = item

    results = []
    score = 0

    for index, question in enumerate(questions):
        expected_answer = normalize_text(question.get("answer", ""))
        submitted_item = submitted_by_index.get(index, {})
        resolved_answer = _resolve_submitted_answer(question, submitted_item)
        submitted_answer = normalize_text(resolved_answer)

        is_correct = bool(submitted_answer) and submitted_answer == expected_answer
        if is_correct:
            score += 1

        results.append(
            {
                "question_index": index,
                "question": question.get("question"),
                "expected_answer": question.get("answer"),
                "submitted_answer": resolved_answer,
                "is_correct": is_correct,
                "type": question.get("type"),
                "question_type": question.get("question_type"),
            }
        )

    return {
        "score": score,
        "total_questions": len(questions),
        "results": results,
    }
