from __future__ import annotations

import csv
import io
from typing import Any

from django.contrib.auth.models import AnonymousUser

from ..models import (
    GoldChangeAnnotation,
    GoldQuizAnnotation,
    GoldSummaryAnnotation,
    Question,
    Summary,
    VersionChangeItem,
    VersionComparison,
)
from ..traceability import build_comparison_trace


def _can_annotate(user) -> bool:
    return bool(user and not isinstance(user, AnonymousUser) and user.is_authenticated)


def _normalize_bool_or_none(value: Any) -> bool | None:
    if value in (None, "", "unknown"):
        return None
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return None


def _normalize_relevance(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in GoldChangeAnnotation.Relevance.values:
        return normalized
    return GoldChangeAnnotation.Relevance.UNKNOWN


def get_or_create_change_annotation(
    change_item: VersionChangeItem,
    user,
) -> GoldChangeAnnotation | None:
    if not _can_annotate(user):
        return None
    annotation, _created = GoldChangeAnnotation.objects.get_or_create(
        change_item=change_item,
        annotator=user,
        defaults={
            "relevance": GoldChangeAnnotation.Relevance.UNKNOWN,
        },
    )
    return annotation


def save_change_annotation(
    change_item: VersionChangeItem,
    user,
    data: dict[str, Any],
) -> GoldChangeAnnotation | None:
    annotation = get_or_create_change_annotation(change_item, user)
    if annotation is None:
        return None
    annotation.corrected_semantic_type = str(
        data.get("corrected_semantic_type") or ""
    ).strip()
    annotation.corrected_significance_label = str(
        data.get("corrected_significance_label") or ""
    ).strip()
    annotation.corrected_requires_manual_review = _normalize_bool_or_none(
        data.get("corrected_requires_manual_review")
    )
    annotation.relevance = _normalize_relevance(data.get("relevance"))
    annotation.is_false_positive = bool(
        _normalize_bool_or_none(data.get("is_false_positive"))
    )
    annotation.comment = str(data.get("comment") or "").strip()
    annotation.save()
    return annotation


def get_or_create_summary_annotation(
    summary: Summary,
    user,
    *,
    highlight_index: int | None,
    source_change_item: VersionChangeItem | None = None,
) -> GoldSummaryAnnotation | None:
    if not _can_annotate(user):
        return None
    annotation, _created = GoldSummaryAnnotation.objects.get_or_create(
        summary=summary,
        annotator=user,
        highlight_index=highlight_index,
        defaults={
            "source_change_item": source_change_item,
            "quality_label": GoldSummaryAnnotation.QualityLabel.GOOD,
        },
    )
    if source_change_item and annotation.source_change_item_id != source_change_item.id:
        annotation.source_change_item = source_change_item
        annotation.save(update_fields=["source_change_item", "updated_at"])
    return annotation


def save_summary_annotation(
    summary: Summary,
    user,
    data: dict[str, Any],
    *,
    source_change_item: VersionChangeItem | None = None,
) -> GoldSummaryAnnotation | None:
    try:
        highlight_index = int(data.get("highlight_index"))
    except (TypeError, ValueError):
        highlight_index = None
    annotation = get_or_create_summary_annotation(
        summary,
        user,
        highlight_index=highlight_index,
        source_change_item=source_change_item,
    )
    if annotation is None:
        return None
    quality_label = str(data.get("quality_label") or "").strip()
    if quality_label not in GoldSummaryAnnotation.QualityLabel.values:
        quality_label = GoldSummaryAnnotation.QualityLabel.GOOD
    annotation.quality_label = quality_label
    annotation.corrected_text = str(data.get("corrected_text") or "").strip()
    annotation.comment = str(data.get("comment") or "").strip()
    if source_change_item is not None:
        annotation.source_change_item = source_change_item
    annotation.save()
    return annotation


def get_or_create_quiz_annotation(question: Question, user) -> GoldQuizAnnotation | None:
    if not _can_annotate(user):
        return None
    annotation, _created = GoldQuizAnnotation.objects.get_or_create(
        question=question,
        annotator=user,
        defaults={"quality_label": GoldQuizAnnotation.QualityLabel.GOOD},
    )
    return annotation


def save_quiz_annotation(
    question: Question,
    user,
    data: dict[str, Any],
) -> GoldQuizAnnotation | None:
    annotation = get_or_create_quiz_annotation(question, user)
    if annotation is None:
        return None
    quality_label = str(data.get("quality_label") or "").strip()
    if quality_label not in GoldQuizAnnotation.QualityLabel.values:
        quality_label = GoldQuizAnnotation.QualityLabel.GOOD
    annotation.quality_label = quality_label
    annotation.corrected_question_text = str(
        data.get("corrected_question_text") or ""
    ).strip()
    annotation.corrected_explanation = str(
        data.get("corrected_explanation") or ""
    ).strip()
    should_keep = _normalize_bool_or_none(data.get("should_keep"))
    annotation.should_keep = True if should_keep is None else bool(should_keep)
    annotation.comment = str(data.get("comment") or "").strip()
    annotation.save()
    return annotation


def collect_annotation_context_for_comparison(
    comparison: VersionComparison,
    user=None,
) -> dict[str, Any]:
    trace_context = build_comparison_trace(comparison)
    trace_items = trace_context["trace_items"]
    try:
        summary_obj = comparison.summary
    except Exception:
        summary_obj = None

    change_annotations = {
        annotation.change_item_id: annotation
        for annotation in GoldChangeAnnotation.objects.filter(
            change_item__comparison=comparison,
            annotator=user,
        )
    } if _can_annotate(user) else {}

    summary_annotations = {
        (annotation.summary_id, annotation.highlight_index): annotation
        for annotation in GoldSummaryAnnotation.objects.filter(
            summary__comparison=comparison,
            annotator=user,
        )
    } if _can_annotate(user) else {}

    quiz_annotations = {
        annotation.question_id: annotation
        for annotation in GoldQuizAnnotation.objects.filter(
            question__quiz__comparison=comparison,
            annotator=user,
        )
    } if _can_annotate(user) else {}

    for item in trace_items:
        item["change_annotation"] = change_annotations.get(item["change_item"].id)
        for summary_link in item["summary_links"]:
            summary_link["annotation"] = summary_annotations.get(
                (summary_obj.id, summary_link["index"])
            ) if summary_obj is not None else None
        for quiz_link in item["quiz_links"]:
            quiz_link["annotation"] = quiz_annotations.get(quiz_link["question_id"])

    annotation_counts = {
        "change_annotations": GoldChangeAnnotation.objects.filter(
            change_item__comparison=comparison
        ).count(),
        "summary_annotations": GoldSummaryAnnotation.objects.filter(
            summary__comparison=comparison
        ).count(),
        "quiz_annotations": GoldQuizAnnotation.objects.filter(
            question__quiz__comparison=comparison
        ).count(),
    }

    return {
        **trace_context,
        "annotation_counts": annotation_counts,
    }


def export_annotations_to_dict() -> dict[str, Any]:
    change_annotations = list(
        GoldChangeAnnotation.objects.select_related(
            "annotator",
            "change_item__comparison__document",
        ).order_by("id")
    )
    summary_annotations = list(
        GoldSummaryAnnotation.objects.select_related(
            "annotator",
            "summary__comparison__document",
            "source_change_item",
        ).order_by("id")
    )
    quiz_annotations = list(
        GoldQuizAnnotation.objects.select_related(
            "annotator",
            "question__quiz__comparison__document",
        ).order_by("id")
    )
    return {
        "change_annotations": [
            {
                "id": item.id,
                "change_item_id": item.change_item_id,
                "comparison_id": item.change_item.comparison_id,
                "document_id": item.change_item.comparison.document_id,
                "annotator_id": item.annotator_id,
                "annotator": item.annotator.username if item.annotator else "",
                "corrected_semantic_type": item.corrected_semantic_type,
                "corrected_significance_label": item.corrected_significance_label,
                "corrected_requires_manual_review": item.corrected_requires_manual_review,
                "relevance": item.relevance,
                "is_false_positive": item.is_false_positive,
                "comment": item.comment,
                "created_at": item.created_at.isoformat(),
                "updated_at": item.updated_at.isoformat(),
            }
            for item in change_annotations
        ],
        "summary_annotations": [
            {
                "id": item.id,
                "summary_id": item.summary_id,
                "comparison_id": item.summary.comparison_id,
                "document_id": item.summary.comparison.document_id,
                "source_change_item_id": item.source_change_item_id,
                "highlight_index": item.highlight_index,
                "annotator_id": item.annotator_id,
                "annotator": item.annotator.username if item.annotator else "",
                "quality_label": item.quality_label,
                "corrected_text": item.corrected_text,
                "comment": item.comment,
                "created_at": item.created_at.isoformat(),
                "updated_at": item.updated_at.isoformat(),
            }
            for item in summary_annotations
        ],
        "quiz_annotations": [
            {
                "id": item.id,
                "question_id": item.question_id,
                "quiz_id": item.question.quiz_id,
                "comparison_id": item.question.quiz.comparison_id,
                "document_id": (
                    item.question.quiz.comparison.document_id
                    if item.question.quiz.comparison_id
                    else None
                ),
                "annotator_id": item.annotator_id,
                "annotator": item.annotator.username if item.annotator else "",
                "quality_label": item.quality_label,
                "corrected_question_text": item.corrected_question_text,
                "corrected_explanation": item.corrected_explanation,
                "should_keep": item.should_keep,
                "comment": item.comment,
                "created_at": item.created_at.isoformat(),
                "updated_at": item.updated_at.isoformat(),
            }
            for item in quiz_annotations
        ],
    }


def export_annotations_to_csv_rows() -> list[dict[str, Any]]:
    payload = export_annotations_to_dict()
    rows: list[dict[str, Any]] = []

    def append_rows(
        annotation_type: str,
        object_id: int | None,
        comparison_id: int | None,
        document_id: int | None,
        annotator: str,
        comment: str,
        created_at: str,
        updated_at: str,
        field_map: dict[str, Any],
    ) -> None:
        for field, value in field_map.items():
            rows.append(
                {
                    "annotation_type": annotation_type,
                    "object_id": object_id,
                    "comparison_id": comparison_id,
                    "document_id": document_id,
                    "annotator": annotator,
                    "field": field,
                    "value": value,
                    "comment": comment,
                    "created_at": created_at,
                    "updated_at": updated_at,
                }
            )

    for item in payload["change_annotations"]:
        append_rows(
            "change",
            item["change_item_id"],
            item["comparison_id"],
            item["document_id"],
            item["annotator"],
            item["comment"],
            item["created_at"],
            item["updated_at"],
            {
                "corrected_semantic_type": item["corrected_semantic_type"],
                "corrected_significance_label": item["corrected_significance_label"],
                "corrected_requires_manual_review": item["corrected_requires_manual_review"],
                "relevance": item["relevance"],
                "is_false_positive": item["is_false_positive"],
            },
        )
    for item in payload["summary_annotations"]:
        append_rows(
            "summary",
            item["summary_id"],
            item["comparison_id"],
            item["document_id"],
            item["annotator"],
            item["comment"],
            item["created_at"],
            item["updated_at"],
            {
                "source_change_item_id": item["source_change_item_id"],
                "highlight_index": item["highlight_index"],
                "quality_label": item["quality_label"],
                "corrected_text": item["corrected_text"],
            },
        )
    for item in payload["quiz_annotations"]:
        append_rows(
            "quiz",
            item["question_id"],
            item["comparison_id"],
            item["document_id"],
            item["annotator"],
            item["comment"],
            item["created_at"],
            item["updated_at"],
            {
                "quiz_id": item["quiz_id"],
                "quality_label": item["quality_label"],
                "corrected_question_text": item["corrected_question_text"],
                "corrected_explanation": item["corrected_explanation"],
                "should_keep": item["should_keep"],
            },
        )
    return rows


def render_annotations_csv() -> str:
    buffer = io.StringIO()
    fieldnames = [
        "annotation_type",
        "object_id",
        "comparison_id",
        "document_id",
        "annotator",
        "field",
        "value",
        "comment",
        "created_at",
        "updated_at",
    ]
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for row in export_annotations_to_csv_rows():
        writer.writerow(row)
    return buffer.getvalue()
