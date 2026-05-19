from __future__ import annotations

from typing import Any

from .models import Answer, Question, VersionChangeItem, VersionComparison


def find_summary_links(change_item: VersionChangeItem) -> list[dict[str, Any]]:
    try:
        summary = change_item.comparison.summary
    except Exception:
        return []

    links: list[dict[str, Any]] = []
    for index, highlight in enumerate(summary.highlights or [], start=1):
        if not isinstance(highlight, dict):
            continue
        if highlight.get("source_change_item_id") != change_item.id:
            continue
        links.append(
            {
                "index": index,
                "title": str(highlight.get("title") or "").strip(),
                "type": str(highlight.get("type") or "").strip(),
                "semantic_type": str(highlight.get("semantic_type") or "").strip(),
                "significance_label": str(
                    highlight.get("significance_label") or ""
                ).strip(),
                "requires_manual_review": bool(
                    highlight.get("requires_manual_review", False)
                ),
                "concise_explanation": str(
                    highlight.get("concise_explanation") or ""
                ).strip(),
                "description": str(highlight.get("description") or "").strip(),
                "source_change_item_id": highlight.get("source_change_item_id"),
            }
        )
    return links


def find_attempt_links(question: Question) -> list[dict[str, Any]]:
    answers = (
        Answer.objects.select_related("attempt", "selected_choice", "attempt__employee")
        .filter(question=question)
        .order_by("-attempt__submitted_at", "-attempt__created_at", "-id")
    )
    links: list[dict[str, Any]] = []
    for answer in answers:
        attempt = answer.attempt
        employee = getattr(attempt, "employee", None)
        links.append(
            {
                "answer_id": answer.id,
                "attempt_id": attempt.id,
                "participant_name": attempt.participant_name,
                "employee_name": employee.full_name if employee else "",
                "selected_choice_text": (
                    answer.selected_choice.text if answer.selected_choice else ""
                ),
                "text_answer": answer.text_answer or "",
                "is_correct": bool(answer.is_correct),
                "score": attempt.score,
                "score_percent": attempt.score_percent,
                "status": attempt.status,
                "submitted_at": attempt.submitted_at,
            }
        )
    return links


def find_quiz_links(change_item: VersionChangeItem) -> list[dict[str, Any]]:
    questions = (
        change_item.questions.select_related("quiz")
        .prefetch_related("choices")
        .order_by("quiz_id", "order", "id")
    )
    links: list[dict[str, Any]] = []
    for question in questions:
        choices = list(question.choices.all().order_by("order", "id"))
        correct_choice = next((choice for choice in choices if choice.is_correct), None)
        links.append(
            {
                "quiz_id": question.quiz_id,
                "quiz_title": question.quiz.title,
                "quiz_status": question.quiz.status,
                "question_id": question.id,
                "question_order": question.order,
                "question_type": question.question_type,
                "prompt": question.prompt,
                "explanation": question.explanation or "",
                "correct_text_answer": question.correct_text_answer or "",
                "choices": [
                    {
                        "id": choice.id,
                        "order": choice.order,
                        "text": choice.text,
                        "is_correct": bool(choice.is_correct),
                    }
                    for choice in choices
                ],
                "correct_choice_text": correct_choice.text if correct_choice else "",
                "attempt_links": find_attempt_links(question),
            }
        )
    return links


def _build_trace_status(
    *,
    has_chunk_link: bool,
    has_summary_link: bool,
    has_quiz_link: bool,
    has_attempt_link: bool,
) -> str:
    if has_chunk_link and has_summary_link and has_quiz_link and has_attempt_link:
        return "complete"
    if not has_summary_link:
        return "missing_summary_link"
    if not has_quiz_link:
        return "missing_quiz_link"
    if not has_attempt_link:
        return "missing_attempt_link"
    return "partial"


def collect_change_trace(change_item: VersionChangeItem) -> dict[str, Any]:
    old_chunk = change_item.old_chunk
    new_chunk = change_item.new_chunk
    summary_links = find_summary_links(change_item)
    quiz_links = find_quiz_links(change_item)
    attempt_links = [
        attempt_link
        for quiz_link in quiz_links
        for attempt_link in quiz_link["attempt_links"]
    ]

    has_chunk_link = old_chunk is not None or new_chunk is not None
    has_summary_link = bool(summary_links)
    has_quiz_link = bool(quiz_links)
    has_attempt_link = bool(attempt_links)

    return {
        "change_item": change_item,
        "change_id": change_item.id,
        "operation_type": change_item.change_type,
        "semantic_type": change_item.semantic_type,
        "significance_label": change_item.significance_label,
        "requires_manual_review": bool(change_item.requires_manual_review),
        "significance_score": change_item.significance_score,
        "significance_reason": change_item.significance_reason,
        "old_text": change_item.old_text or "",
        "new_text": change_item.new_text or "",
        "old_chunk": old_chunk,
        "new_chunk": new_chunk,
        "display_title": (
            (new_chunk.heading if new_chunk and new_chunk.heading else "")
            or (old_chunk.heading if old_chunk and old_chunk.heading else "")
            or (
                new_chunk.section_path
                if new_chunk and new_chunk.section_path
                else ""
            )
            or (
                old_chunk.section_path
                if old_chunk and old_chunk.section_path
                else ""
            )
            or "Trace item"
        ),
        "source_chunk_ids": [chunk.id for chunk in (old_chunk, new_chunk) if chunk],
        "has_chunk_link": has_chunk_link,
        "summary_links": summary_links,
        "quiz_links": quiz_links,
        "attempt_links": attempt_links,
        "trace_status": _build_trace_status(
            has_chunk_link=has_chunk_link,
            has_summary_link=has_summary_link,
            has_quiz_link=has_quiz_link,
            has_attempt_link=has_attempt_link,
        ),
    }


def calculate_trace_completeness(
    trace_items: list[dict[str, Any]],
) -> dict[str, int]:
    summary = {
        "total_changes": len(trace_items),
        "changes_with_summary_link": 0,
        "changes_with_quiz_link": 0,
        "changes_with_attempts": 0,
        "complete_traces": 0,
        "partial_traces": 0,
    }
    for item in trace_items:
        if item.get("summary_links"):
            summary["changes_with_summary_link"] += 1
        if item.get("quiz_links"):
            summary["changes_with_quiz_link"] += 1
        if item.get("attempt_links"):
            summary["changes_with_attempts"] += 1
        if item.get("trace_status") == "complete":
            summary["complete_traces"] += 1
        else:
            summary["partial_traces"] += 1
    return summary


def build_comparison_trace(comparison: VersionComparison) -> dict[str, Any]:
    change_items = list(
        comparison.change_items.select_related("old_chunk", "new_chunk").order_by(
            "sort_order", "id"
        )
    )
    trace_items = [collect_change_trace(change_item) for change_item in change_items]
    completeness = calculate_trace_completeness(trace_items)
    attempt_ids = {
        attempt_link["attempt_id"]
        for trace_item in trace_items
        for attempt_link in trace_item["attempt_links"]
    }
    quiz_ids = {
        quiz_link["quiz_id"]
        for trace_item in trace_items
        for quiz_link in trace_item["quiz_links"]
    }
    significant_labels = {"critical", "important", "informational", "minor"}
    significant_changes = sum(
        1
        for item in trace_items
        if str(item.get("significance_label") or "").strip().lower()
        in significant_labels
    )

    return {
        "comparison": comparison,
        "trace_items": trace_items,
        "trace_summary": completeness,
        "counts": {
            "changes": len(trace_items),
            "significant_changes": significant_changes,
            "quiz_questions": sum(len(item["quiz_links"]) for item in trace_items),
            "attempts": len(attempt_ids),
            "quizzes": len(quiz_ids),
        },
    }
