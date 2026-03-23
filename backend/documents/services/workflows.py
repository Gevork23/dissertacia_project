from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from ..domain.diff import build_version_diff
from ..domain.diff_quiz import build_quiz_from_diff
from ..domain.diff_summary import build_brief_summary
from ..models import (
    Answer,
    Choice,
    Chunk,
    DocumentVersion,
    GeneratedQuiz,
    Question,
    QuizAttempt,
    Summary,
    VersionChangeItem,
    VersionComparison,
)
from .quiz_attempts import evaluate_quiz_answers, resolve_submitted_answer


class EmptyQuizError(ValueError):
    pass


class DomainWorkflowError(ValueError):
    pass


QUESTION_TYPE_MAP = {
    "open_text": Question.QuestionType.TEXT,
    "text": Question.QuestionType.TEXT,
    "single_choice": Question.QuestionType.SINGLE_CHOICE,
}


CHANGE_TYPE_TO_MODEL = {
    "added": VersionChangeItem.ChangeType.ADDED,
    "removed": VersionChangeItem.ChangeType.REMOVED,
    "modified": VersionChangeItem.ChangeType.MODIFIED,
    "moved": VersionChangeItem.ChangeType.MOVED,
}


def make_json_safe(value: Any):
    if isinstance(value, dict):
        return {key: make_json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [make_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [make_json_safe(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _validate_version_pair(
    from_version: DocumentVersion, to_version: DocumentVersion
) -> None:
    if from_version.document_id != to_version.document_id:
        raise DomainWorkflowError("Versions must belong to the same document.")
    if from_version.version_number >= to_version.version_number:
        raise DomainWorkflowError("Target version must be newer than source version.")


def _get_chunk(chunk_payload: dict[str, Any] | None) -> Chunk | None:
    if not chunk_payload:
        return None
    chunk_id = chunk_payload.get("id")
    if not chunk_id:
        return None
    return Chunk.objects.get(pk=chunk_id)


@transaction.atomic
def materialize_comparison(
    *,
    from_version: DocumentVersion,
    to_version: DocumentVersion,
    diff_payload: dict[str, Any] | None = None,
) -> tuple[VersionComparison, Summary, dict[str, Any], list[VersionChangeItem]]:
    _validate_version_pair(from_version=from_version, to_version=to_version)

    diff_payload = diff_payload or build_version_diff(
        from_version=from_version,
        to_version=to_version,
    )
    brief_payload = build_brief_summary(diff_payload)

    comparison, _ = VersionComparison.objects.update_or_create(
        from_version=from_version,
        to_version=to_version,
        defaults={
            "document": from_version.document,
            "status": VersionComparison.Status.DRAFT,
        },
    )

    comparison.change_items.all().delete()
    change_items: list[VersionChangeItem] = []
    sort_order = 1

    for chunk in diff_payload.get("added", []):
        change_items.append(
            VersionChangeItem.objects.create(
                comparison=comparison,
                change_type=VersionChangeItem.ChangeType.ADDED,
                new_chunk=_get_chunk(chunk),
                sort_order=sort_order,
            )
        )
        sort_order += 1

    for item in diff_payload.get("modified", []):
        change_items.append(
            VersionChangeItem.objects.create(
                comparison=comparison,
                change_type=VersionChangeItem.ChangeType.MODIFIED,
                old_chunk=_get_chunk(item.get("from_chunk")),
                new_chunk=_get_chunk(item.get("to_chunk")),
                similarity=item.get("similarity"),
                match_reason=item.get("match_reason") or "",
                sort_order=sort_order,
            )
        )
        sort_order += 1

    for chunk in diff_payload.get("removed", []):
        change_items.append(
            VersionChangeItem.objects.create(
                comparison=comparison,
                change_type=VersionChangeItem.ChangeType.REMOVED,
                old_chunk=_get_chunk(chunk),
                sort_order=sort_order,
            )
        )
        sort_order += 1

    for item in diff_payload.get("moved", []):
        change_items.append(
            VersionChangeItem.objects.create(
                comparison=comparison,
                change_type=VersionChangeItem.ChangeType.MOVED,
                old_chunk=_get_chunk(item.get("from_chunk")),
                new_chunk=_get_chunk(item.get("to_chunk")),
                match_reason="moved",
                sort_order=sort_order,
            )
        )
        sort_order += 1

    comparison.status = VersionComparison.Status.COMPLETED
    comparison.save(update_fields=["document", "status", "updated_at"])

    summary, _ = Summary.objects.update_or_create(
        comparison=comparison,
        defaults={
            "text": brief_payload["brief_text"],
            "highlights": make_json_safe(brief_payload["highlights"]),
        },
    )

    return comparison, summary, diff_payload, change_items


@transaction.atomic
def create_quiz_from_versions(
    *,
    from_version: DocumentVersion,
    to_version: DocumentVersion,
    title: str,
    max_questions: int = 10,
) -> GeneratedQuiz:
    diff_payload = build_version_diff(from_version=from_version, to_version=to_version)
    comparison, summary, diff_payload, change_items = materialize_comparison(
        from_version=from_version,
        to_version=to_version,
        diff_payload=diff_payload,
    )
    quiz_payload = make_json_safe(
        build_quiz_from_diff(diff_payload=diff_payload, max_questions=max_questions)
    )

    if quiz_payload["questions_count"] == 0:
        raise EmptyQuizError(
            "Quiz was not saved because there are no changes between the selected versions."
        )

    quiz = GeneratedQuiz.objects.create(
        comparison=comparison,
        summary=summary,
        from_version=from_version,
        to_version=to_version,
        title=title,
        payload=quiz_payload,
        questions_count=quiz_payload["questions_count"],
    )

    materialized_change_items = change_items[: quiz_payload["questions_count"]]

    for index, (question_payload, change_item) in enumerate(
        zip(quiz_payload.get("questions", []), materialized_change_items),
        start=1,
    ):
        question = Question.objects.create(
            quiz=quiz,
            source_change_item=change_item,
            order=index,
            question_type=QUESTION_TYPE_MAP.get(
                question_payload.get("question_type"),
                Question.QuestionType.TEXT,
            ),
            prompt=question_payload.get("question", ""),
            correct_text_answer=question_payload.get("answer", ""),
            explanation=question_payload.get("type", ""),
        )

        for choice_index, choice_payload in enumerate(
            question_payload.get("choices", []),
        ):
            order = choice_payload.get("choice_index")
            if order is None:
                order = choice_index
            Choice.objects.create(
                question=question,
                order=int(order),
                text=choice_payload.get("text", ""),
                is_correct=bool(choice_payload.get("is_correct", False)),
            )

    return quiz


@transaction.atomic
def record_quiz_attempt(
    *,
    quiz: GeneratedQuiz,
    participant_name: str,
    submitted_answers: list[dict[str, Any]],
) -> tuple[QuizAttempt, dict[str, Any]]:
    evaluation = evaluate_quiz_answers(
        quiz_payload=quiz.payload,
        submitted_answers=submitted_answers,
    )
    stored_answers = make_json_safe(evaluation["results"])

    attempt = QuizAttempt.objects.create(
        quiz=quiz,
        participant_name=participant_name,
        answers=stored_answers,
        score=evaluation["score"],
        total_questions=evaluation["total_questions"],
        status=QuizAttempt.Status.COMPLETED,
        completed_at=timezone.now(),
    )

    questions = list(quiz.questions.prefetch_related("choices").order_by("order", "id"))
    if not questions:
        return attempt, evaluation

    payload_questions = quiz.payload.get("questions", [])
    submitted_by_index: dict[int, dict[str, Any]] = {}
    for item in submitted_answers:
        try:
            question_index = int(item.get("question_index"))
        except (TypeError, ValueError):
            continue
        submitted_by_index[question_index] = item

    for index, question in enumerate(questions):
        payload_question = (
            payload_questions[index] if index < len(payload_questions) else {}
        )
        submitted_item = submitted_by_index.get(index, {})
        resolved_answer = resolve_submitted_answer(payload_question, submitted_item)

        selected_choice = None
        if question.question_type == Question.QuestionType.SINGLE_CHOICE:
            choice_index = submitted_item.get("selected_choice_index")
            if choice_index is not None:
                try:
                    selected_choice = question.choices.get(order=int(choice_index))
                except (Choice.DoesNotExist, TypeError, ValueError):
                    selected_choice = None

            if selected_choice is None:
                selected_choice_text = (
                    submitted_item.get("selected_choice_text") or resolved_answer
                )
                if selected_choice_text:
                    selected_choice = question.choices.filter(
                        text=str(selected_choice_text)
                    ).first()

        Answer.objects.create(
            attempt=attempt,
            question=question,
            selected_choice=selected_choice,
            text_answer="" if selected_choice is not None else resolved_answer,
            is_correct=bool(stored_answers[index]["is_correct"]),
        )

    return attempt, evaluation
