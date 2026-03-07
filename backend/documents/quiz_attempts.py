from __future__ import annotations


def normalize_text(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


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
        submitted_answer = normalize_text(submitted_item.get("answer", ""))

        is_correct = bool(submitted_answer) and submitted_answer == expected_answer
        if is_correct:
            score += 1

        results.append(
            {
                "question_index": index,
                "question": question.get("question"),
                "expected_answer": question.get("answer"),
                "submitted_answer": submitted_item.get("answer", ""),
                "is_correct": is_correct,
                "type": question.get("type"),
            }
        )

    return {
        "score": score,
        "total_questions": len(questions),
        "results": results,
    }
