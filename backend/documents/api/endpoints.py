from __future__ import annotations

import logging

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from ..domain.change_enrichment import enrich_compare_payload
from ..domain.diff import build_version_diff
from ..domain.diff_quiz import build_quiz_from_diff
from ..domain.diff_summary import build_brief_summary
from ..models import DocumentVersion, GeneratedQuiz
from ..services.search import search_chunks
from ..services.workflows import (
    EmptyQuizError,
    create_quiz_from_versions,
    record_quiz_attempt,
)
from .serializers import (
    GeneratedQuizSerializer,
    QuizAttemptSerializer,
    VersionDiffSerializer,
)

logger = logging.getLogger("documents.api")


def build_quiz_report_payload(quiz: GeneratedQuiz) -> dict:
    attempts = list(quiz.attempts.order_by("-created_at"))
    attempts_count = len(attempts)
    scores = [attempt.score for attempt in attempts]
    totals = [
        attempt.total_questions for attempt in attempts if attempt.total_questions
    ]
    average_score = round(sum(scores) / attempts_count, 2) if attempts_count else 0.0
    average_percentage = (
        round(
            sum(
                (attempt.score / attempt.total_questions) * 100
                for attempt in attempts
                if attempt.total_questions
            )
            / len(totals),
            2,
        )
        if totals
        else 0.0
    )

    return {
        "quiz": GeneratedQuizSerializer(quiz).data,
        "attempts_count": attempts_count,
        "average_score": average_score,
        "average_percentage": average_percentage,
        "best_score": max(scores) if scores else 0,
        "latest_attempts": QuizAttemptSerializer(attempts[:10], many=True).data,
    }


@api_view(["GET"])
def search(request):
    if not settings.QDRANT_ENABLED:
        return Response(
            {
                "detail": (
                    "Semantic search is disabled in the current backend profile. "
                    "Set QDRANT_ENABLED=1 to enable it."
                )
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    q = (request.query_params.get("q") or "").strip()
    if not q:
        logger.warning("Search rejected: empty q")
        return Response(
            {"detail": "Query parameter 'q' is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        limit = int(request.query_params.get("limit", 5))
    except ValueError:
        limit = 5

    document_id = request.query_params.get("document_id")
    version_id = request.query_params.get("version_id")

    latest_only_raw = (
        (request.query_params.get("latest_only") or "true").strip().lower()
    )
    latest_only = latest_only_raw not in {"0", "false", "no"}

    logger.info(
        "Search request: q=%r limit=%s document_id=%s version_id=%s latest_only=%s",
        q,
        limit,
        document_id,
        version_id,
        latest_only,
    )

    results = search_chunks(
        query=q,
        limit=min(max(limit, 1), 20),
        document_id=int(document_id) if document_id else None,
        version_id=int(version_id) if version_id else None,
        latest_only=latest_only,
    )

    logger.info("Search response: q=%r count=%s", q, len(results))
    return Response({"query": q, "count": len(results), "results": results})


def _get_request_value(request, name: str) -> str | None:
    if request.method == "GET":
        value = request.query_params.get(name)
    else:
        value = request.data.get(name)
        if value is None:
            value = request.query_params.get(name)

    if value is None:
        return None

    return str(value).strip()


def _get_versions_for_compare(request):
    from_version_raw = _get_request_value(request, "from_version")
    to_version_raw = _get_request_value(request, "to_version")

    if not from_version_raw or not to_version_raw:
        if request.method == "GET":
            detail = "Query parameters 'from_version' and 'to_version' are required."
        else:
            detail = "Parameters 'from_version' and 'to_version' are required."

        return (
            None,
            None,
            Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST),
        )

    try:
        from_version_id = int(from_version_raw)
        to_version_id = int(to_version_raw)
    except ValueError:
        return (
            None,
            None,
            Response(
                {
                    "detail": (
                        "Parameters 'from_version' and 'to_version' "
                        "must be integers."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            ),
        )

    version_from = get_object_or_404(
        DocumentVersion.objects.select_related("document").prefetch_related("chunks"),
        pk=from_version_id,
    )
    version_to = get_object_or_404(
        DocumentVersion.objects.select_related("document").prefetch_related("chunks"),
        pk=to_version_id,
    )

    if version_from.document_id != version_to.document_id:
        return (
            None,
            None,
            Response(
                {"detail": "Versions must belong to the same document."},
                status=status.HTTP_400_BAD_REQUEST,
            ),
        )

    return version_from, version_to, None


@api_view(["GET"])
def compare_versions(request):
    version_from, version_to, error_response = _get_versions_for_compare(request)
    if error_response is not None:
        return error_response

    logger.info(
        "Compare versions request: from_version_id=%s to_version_id=%s document_id=%s",
        version_from.id,
        version_to.id,
        version_from.document_id,
    )

    diff_payload = build_version_diff(
        from_version=version_from,
        to_version=version_to,
    )
    serializer = VersionDiffSerializer(diff_payload)
    response_payload = enrich_compare_payload(serializer.data)

    logger.info(
        "Compare versions response: from_version_id=%s to_version_id=%s "
        "added=%s removed=%s modified=%s moved=%s unchanged=%s",
        version_from.id,
        version_to.id,
        response_payload["summary"]["added"],
        response_payload["summary"]["removed"],
        response_payload["summary"]["modified"],
        response_payload["summary"]["moved"],
        response_payload["summary"]["unchanged"],
    )

    return Response(response_payload, status=status.HTTP_200_OK)


@api_view(["GET"])
def compare_versions_brief(request):
    version_from, version_to, error_response = _get_versions_for_compare(request)
    if error_response is not None:
        return error_response

    logger.info(
        "Compare versions brief request: from_version_id=%s to_version_id=%s "
        "document_id=%s",
        version_from.id,
        version_to.id,
        version_from.document_id,
    )

    diff_payload = build_version_diff(
        from_version=version_from,
        to_version=version_to,
    )
    brief_payload = build_brief_summary(diff_payload)

    logger.info(
        "Compare versions brief response: from_version_id=%s to_version_id=%s "
        "highlights=%s",
        version_from.id,
        version_to.id,
        len(brief_payload["highlights"]),
    )

    return Response(brief_payload, status=status.HTTP_200_OK)


@api_view(["GET"])
def compare_versions_quiz(request):
    version_from, version_to, error_response = _get_versions_for_compare(request)
    if error_response is not None:
        return error_response

    try:
        max_questions = int(request.query_params.get("limit", 10))
    except ValueError:
        max_questions = 10

    max_questions = min(max(max_questions, 1), 20)

    logger.info(
        "Compare versions quiz request: from_version_id=%s to_version_id=%s "
        "document_id=%s limit=%s",
        version_from.id,
        version_to.id,
        version_from.document_id,
        max_questions,
    )

    diff_payload = build_version_diff(
        from_version=version_from,
        to_version=version_to,
    )
    quiz_payload = build_quiz_from_diff(
        diff_payload=diff_payload,
        max_questions=max_questions,
    )

    logger.info(
        "Compare versions quiz response: from_version_id=%s to_version_id=%s "
        "questions=%s",
        version_from.id,
        version_to.id,
        quiz_payload["questions_count"],
    )

    return Response(quiz_payload, status=status.HTTP_200_OK)


@api_view(["POST"])
def save_versions_quiz(request):
    version_from, version_to, error_response = _get_versions_for_compare(request)
    if error_response is not None:
        return error_response

    try:
        max_questions = int(request.data.get("limit", 10))
    except (TypeError, ValueError):
        max_questions = 10

    max_questions = min(max(max_questions, 1), 20)

    title = (request.data.get("title") or "").strip()

    if not title:
        title = (
            f"Quiz for versions "
            f"{version_from.version_number} -> {version_to.version_number}"
        )

    try:
        generated_quiz = create_quiz_from_versions(
            from_version=version_from,
            to_version=version_to,
            title=title,
            max_questions=max_questions,
        )
    except EmptyQuizError as error:
        return Response(
            {"detail": str(error)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    logger.info(
        "Quiz saved: quiz_id=%s from_version_id=%s to_version_id=%s questions=%s",
        generated_quiz.id,
        version_from.id,
        version_to.id,
        generated_quiz.questions_count,
    )

    serializer = GeneratedQuizSerializer(generated_quiz)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
def list_saved_quizzes(request):
    queryset = GeneratedQuiz.objects.select_related(
        "from_version",
        "to_version",
    ).order_by("-created_at")

    serializer = GeneratedQuizSerializer(queryset, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["POST"])
def approve_quiz(request, quiz_id: int):
    quiz = get_object_or_404(GeneratedQuiz, pk=quiz_id)
    approved_by_name = (request.data.get("approved_by_name") or "").strip()
    approval_comment = (request.data.get("approval_comment") or "").strip()

    if not approved_by_name:
        return Response(
            {"detail": "Field 'approved_by_name' is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    quiz.status = GeneratedQuiz.Status.APPROVED
    quiz.approved_by_name = approved_by_name
    quiz.approved_at = timezone.now()
    quiz.approval_comment = approval_comment
    quiz.save(
        update_fields=[
            "status",
            "approved_by_name",
            "approved_at",
            "approval_comment",
            "updated_at",
        ]
    )

    logger.info("Quiz approved: quiz_id=%s approved_by=%s", quiz.id, approved_by_name)
    return Response(GeneratedQuizSerializer(quiz).data, status=status.HTTP_200_OK)


@api_view(["POST"])
def submit_quiz_attempt(request, quiz_id: int):
    quiz = get_object_or_404(GeneratedQuiz, pk=quiz_id)

    if quiz.status != GeneratedQuiz.Status.APPROVED:
        return Response(
            {"detail": "Quiz must be approved before it can be assigned."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if quiz.questions_count == 0:
        return Response(
            {"detail": "Cannot submit an attempt for an empty quiz."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    participant_name = (request.data.get("participant_name") or "").strip()
    answers = request.data.get("answers") or []

    if not isinstance(answers, list):
        return Response(
            {"detail": "Field 'answers' must be a list."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    attempt, evaluation = record_quiz_attempt(
        quiz=quiz,
        participant_name=participant_name,
        submitted_answers=answers,
    )

    logger.info(
        "Quiz attempt saved: attempt_id=%s quiz_id=%s score=%s total=%s",
        attempt.id,
        quiz.id,
        attempt.score,
        attempt.total_questions,
    )

    serializer = QuizAttemptSerializer(attempt)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
def list_quiz_attempts(request, quiz_id: int):
    quiz = get_object_or_404(GeneratedQuiz, pk=quiz_id)
    queryset = quiz.attempts.all().order_by("-created_at")

    serializer = QuizAttemptSerializer(queryset, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["GET"])
def quiz_report(request, quiz_id: int):
    quiz = get_object_or_404(GeneratedQuiz, pk=quiz_id)
    return Response(build_quiz_report_payload(quiz), status=status.HTTP_200_OK)
