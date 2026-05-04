from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from django.db import transaction

from ..domain.change_enrichment import enrich_compare_payload
from ..domain.diff import (
    build_version_diff,
    iter_ordered_change_entries,
    validate_version_pair,
)
from ..domain.diff_quiz import build_quiz_from_summary
from ..domain.diff_summary import build_brief_summary
from ..models import (
    Choice,
    Chunk,
    DocumentVersion,
    GeneratedQuiz,
    Question,
    Summary,
    VersionChangeItem,
    VersionComparison,
)
from . import quiz_attempts as quiz_attempt_services
from . import quiz_workflow as quiz_workflow_services
from .exceptions import DomainWorkflowError


class EmptyQuizError(ValueError):
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


def get_quiz_attempt_block_reason(quiz: GeneratedQuiz) -> str | None:
    """Compatibility wrapper: quiz availability is owned by quiz_workflow.py."""
    return quiz_workflow_services.get_quiz_attempt_block_reason(quiz)


def ensure_quiz_attempt_allowed(quiz: GeneratedQuiz) -> None:
    """Compatibility wrapper: quiz availability is owned by quiz_workflow.py."""
    quiz_workflow_services.ensure_quiz_attempt_allowed(quiz)


def submit_quiz_for_review(quiz: GeneratedQuiz) -> GeneratedQuiz:
    """Compatibility wrapper: quiz lifecycle is owned by quiz_workflow.py."""
    return quiz_workflow_services.submit_quiz_for_review(quiz)


def approve_generated_quiz(
    *,
    quiz: GeneratedQuiz,
    approved_by_name: str,
    approval_comment: str = "",
) -> GeneratedQuiz:
    """Compatibility wrapper: quiz lifecycle is owned by quiz_workflow.py."""
    return quiz_workflow_services.approve_generated_quiz(
        quiz=quiz,
        approved_by_name=approved_by_name,
        approval_comment=approval_comment,
    )


def reject_generated_quiz(
    *,
    quiz: GeneratedQuiz,
    rejected_by_name: str,
    rejection_comment: str = "",
) -> GeneratedQuiz:
    """Compatibility wrapper: quiz lifecycle is owned by quiz_workflow.py."""
    return quiz_workflow_services.reject_generated_quiz(
        quiz=quiz,
        rejected_by_name=rejected_by_name,
        rejection_comment=rejection_comment,
    )


def mark_quiz_superseded(quiz: GeneratedQuiz, *, reason: str = "") -> GeneratedQuiz:
    """Compatibility wrapper: quiz lifecycle is owned by quiz_workflow.py."""
    return quiz_workflow_services.mark_quiz_superseded(quiz, reason=reason)


def _supersede_existing_quizzes_for_version_pair(
    *,
    from_version: DocumentVersion,
    to_version: DocumentVersion,
    exclude_quiz_id: int,
    reason: str,
) -> None:
    queryset = GeneratedQuiz.objects.filter(
        from_version=from_version,
        to_version=to_version,
        status__in=[
            GeneratedQuiz.Status.DRAFT,
            GeneratedQuiz.Status.PENDING_REVIEW,
            GeneratedQuiz.Status.APPROVED,
        ],
    ).exclude(pk=exclude_quiz_id)

    for existing_quiz in queryset:
        mark_quiz_superseded(existing_quiz, reason=reason)


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
        build_quiz_from_summary(
            summary_payload={"highlights": summary.highlights},
            from_version=diff_payload["from_version"],
            to_version=diff_payload["to_version"],
            identical=bool(diff_payload.get("identical", False)),
            max_questions=max_questions,
        )
    )

    if quiz_payload["questions_count"] == 0:
        raise EmptyQuizError(
            "Quiz was not saved because there are no changes or not enough significant changes for a meaningful knowledge check between the selected versions."
        )

    quiz = GeneratedQuiz.objects.create(
        comparison=comparison,
        summary=summary,
        from_version=from_version,
        to_version=to_version,
        title=title,
        payload=quiz_payload,
        questions_count=quiz_payload["questions_count"],
        status=GeneratedQuiz.Status.DRAFT,
    )

    materialized_change_items_by_id = {item.id: item for item in change_items}
    fallback_change_items = iter(change_items)

    for index, question_payload in enumerate(
        quiz_payload.get("questions", []),
        start=1,
    ):
        change_item = materialized_change_items_by_id.get(
            question_payload.get("source_change_item_id")
        )
        if change_item is None:
            change_item = next(fallback_change_items, None)

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
                question_payload.get("explanation")
                or question_payload.get("significance_reason")
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

    _supersede_existing_quizzes_for_version_pair(
        from_version=from_version,
        to_version=to_version,
        exclude_quiz_id=quiz.id,
        reason="A newer quiz draft was generated for the same version pair.",
    )

    return quiz


def start_quiz_attempt(
    *,
    quiz: GeneratedQuiz,
    participant_name: str,
    employee=None,
):
    """Compatibility wrapper: attempt execution is owned by quiz_attempts.py."""
    return quiz_attempt_services.start_quiz_attempt(
        quiz=quiz,
        participant_name=participant_name,
        employee=employee,
    )


def submit_started_quiz_attempt(
    *,
    attempt,
    submitted_answers: list[dict[str, Any]],
):
    """Compatibility wrapper: attempt execution is owned by quiz_attempts.py."""
    return quiz_attempt_services.submit_started_quiz_attempt(
        attempt=attempt,
        submitted_answers=submitted_answers,
    )


def record_quiz_attempt(
    *,
    quiz: GeneratedQuiz,
    participant_name: str,
    submitted_answers: list[dict[str, Any]],
):
    """Compatibility wrapper: attempt execution is owned by quiz_attempts.py."""
    return quiz_attempt_services.record_quiz_attempt(
        quiz=quiz,
        participant_name=participant_name,
        submitted_answers=submitted_answers,
    )
