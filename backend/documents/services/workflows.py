from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from ..domain.change_enrichment import (
    enrich_compare_payload,
    select_prioritized_change_items,
)
from ..domain.diff import (
    build_version_diff,
    iter_ordered_change_entries,
    validate_version_pair,
)
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


def build_comparison_payload(
    *,
    from_version: DocumentVersion,
    to_version: DocumentVersion,
) -> dict[str, Any]:
    try:
        validate_version_pair(from_version=from_version, to_version=to_version)
    except ValueError as error:
        raise DomainWorkflowError(str(error)) from error
    return build_version_diff(from_version=from_version, to_version=to_version)


def _get_chunk(chunk_payload: dict[str, Any] | None) -> Chunk | None:
    if not chunk_payload:
        return None
    chunk_id = chunk_payload.get("id")
    if not chunk_id:
        return None
    return Chunk.objects.get(pk=chunk_id)


def _get_chunk_text(chunk_payload: dict[str, Any] | None) -> str:
    if not chunk_payload:
        return ""
    return str(chunk_payload.get("text") or "")


def _attach_summary_source_refs(
    highlights: list[dict[str, Any]],
    change_items: list[VersionChangeItem],
) -> list[dict[str, Any]]:
    if not highlights:
        return []

    change_items_by_sort_order = {item.sort_order: item for item in change_items}
    resolved: list[dict[str, Any]] = []

    for highlight in highlights:
        item = dict(highlight)
        source_sort_order = item.get("source_sort_order")
        try:
            sort_order = int(source_sort_order)
        except (TypeError, ValueError):
            sort_order = None

        source_change_item = None
        if sort_order is not None:
            source_change_item = change_items_by_sort_order.get(sort_order)

        item["source_change_item_id"] = (
            source_change_item.id if source_change_item is not None else None
        )
        resolved.append(item)

    return resolved


@transaction.atomic
def materialize_comparison(
    *,
    from_version: DocumentVersion,
    to_version: DocumentVersion,
    diff_payload: dict[str, Any] | None = None,
) -> tuple[VersionComparison, Summary, dict[str, Any], list[VersionChangeItem]]:
    raw_diff_payload = diff_payload or build_comparison_payload(
        from_version=from_version,
        to_version=to_version,
    )
    diff_payload = enrich_compare_payload(raw_diff_payload)
    brief_payload = build_brief_summary(diff_payload)
    comparison_meta = diff_payload.get("comparison_meta") or {}
    summary_payload = diff_payload.get("summary") or {}

    comparison, _ = VersionComparison.objects.update_or_create(
        from_version=from_version,
        to_version=to_version,
        defaults={
            "document": from_version.document,
            "status": VersionComparison.Status.DRAFT,
            "comparison_unit": comparison_meta.get(
                "comparison_unit",
                VersionComparison.ComparisonUnit.CHUNK,
            ),
            "matching_strategy": comparison_meta.get(
                "matching_strategy",
                "structural_chunks_v2",
            ),
            "identical": bool(diff_payload.get("identical", False)),
            "added_count": int(summary_payload.get("added", 0)),
            "removed_count": int(summary_payload.get("removed", 0)),
            "modified_count": int(summary_payload.get("modified", 0)),
            "moved_count": int(summary_payload.get("moved", 0)),
            "unchanged_count": int(summary_payload.get("unchanged", 0)),
        },
    )

    comparison.change_items.all().delete()
    change_items: list[VersionChangeItem] = []

    for sort_order, (change_type, payload) in enumerate(
        iter_ordered_change_entries(diff_payload),
        start=1,
    ):
        old_payload = None
        new_payload = None
        if change_type in {"modified", "moved"}:
            old_payload = payload.get("from_chunk")
            new_payload = payload.get("to_chunk")
        elif change_type == "removed":
            old_payload = payload
        else:
            new_payload = payload

        item_kwargs = {
            "comparison": comparison,
            "change_type": CHANGE_TYPE_TO_MODEL[change_type],
            "old_chunk": _get_chunk(old_payload),
            "new_chunk": _get_chunk(new_payload),
            "old_text": _get_chunk_text(old_payload),
            "new_text": _get_chunk_text(new_payload),
            "semantic_type": payload.get("semantic_type")
            or VersionChangeItem.SemanticType.UNCLASSIFIED,
            "extracted_entities": make_json_safe(
                payload.get("extracted_entities") or []
            ),
            "significance_label": payload.get("significance_label")
            or VersionChangeItem.SignificanceLabel.NOT_EVALUATED,
            "significance_score": float(payload.get("significance_score") or 0.0),
            "significance_reason": payload.get("significance_reason") or "",
            "significance_rules": make_json_safe(
                payload.get("significance_rules")
                or payload.get("importance_triggered_rules")
                or []
            ),
            "requires_manual_review": bool(
                payload.get("requires_manual_review", False)
            ),
            "sort_order": sort_order,
        }
        if change_type in {"modified", "moved"}:
            item_kwargs["similarity"] = payload.get("similarity")
            item_kwargs["match_reason"] = payload.get("match_reason") or change_type
        change_items.append(VersionChangeItem.objects.create(**item_kwargs))

    comparison.status = VersionComparison.Status.COMPLETED
    comparison.comparison_unit = comparison_meta.get(
        "comparison_unit", comparison.comparison_unit
    )
    comparison.matching_strategy = comparison_meta.get(
        "matching_strategy", comparison.matching_strategy
    )
    comparison.identical = bool(diff_payload.get("identical", False))
    comparison.added_count = int(summary_payload.get("added", 0))
    comparison.removed_count = int(summary_payload.get("removed", 0))
    comparison.modified_count = int(summary_payload.get("modified", 0))
    comparison.moved_count = int(summary_payload.get("moved", 0))
    comparison.unchanged_count = int(summary_payload.get("unchanged", 0))
    comparison.save(
        update_fields=[
            "document",
            "status",
            "comparison_unit",
            "matching_strategy",
            "identical",
            "added_count",
            "removed_count",
            "modified_count",
            "moved_count",
            "unchanged_count",
            "updated_at",
        ]
    )

    resolved_highlights = _attach_summary_source_refs(
        brief_payload["highlights"],
        change_items,
    )

    summary, _ = Summary.objects.update_or_create(
        comparison=comparison,
        defaults={
            "text": brief_payload["brief_text"],
            "highlights": make_json_safe(resolved_highlights),
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
    diff_payload = build_comparison_payload(
        from_version=from_version, to_version=to_version
    )
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

    materialized_change_items = select_prioritized_change_items(
        change_items,
        limit=quiz_payload["questions_count"],
        prefer_non_editorial=True,
    )

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
            explanation=(
                question_payload.get("significance_reason")
                or question_payload.get("type", "")
            ),
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
