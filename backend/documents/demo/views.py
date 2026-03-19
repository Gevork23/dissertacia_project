from __future__ import annotations

from typing import Any

from django.contrib import messages
from django.db.models import Count, Max
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods

from ..api.endpoints import build_quiz_report_payload
from ..api.serializers import VersionDiffSerializer
from ..domain.change_enrichment import enrich_compare_payload
from ..domain.diff import build_version_diff
from ..domain.diff_quiz import build_quiz_from_diff
from ..domain.diff_summary import build_brief_summary
from ..models import Document, DocumentVersion, GeneratedQuiz, QuizAttempt
from ..services.quiz_attempts import evaluate_quiz_answers

DEMO_DOCUMENT_TITLE_PREFIX = "DEMO МФЦ:"


def _load_document_with_stats(document_id: int) -> Document:
    return get_object_or_404(
        Document.objects.annotate(
            versions_count=Count("versions"),
            latest_version_number=Max("versions__version_number"),
        ),
        pk=document_id,
    )


def _build_compare_context(
    *,
    from_version: DocumentVersion,
    to_version: DocumentVersion,
) -> dict[str, Any]:
    diff_payload = build_version_diff(from_version=from_version, to_version=to_version)
    serialized_diff = VersionDiffSerializer(diff_payload).data
    enriched_diff = enrich_compare_payload(serialized_diff)
    brief_payload = build_brief_summary(enriched_diff)
    quiz_preview = build_quiz_from_diff(diff_payload, max_questions=10)

    return {
        "diff": enriched_diff,
        "brief": brief_payload,
        "quiz_preview": quiz_preview,
    }


@require_GET
def dashboard(request: HttpRequest) -> HttpResponse:
    documents = (
        Document.objects.filter(title__startswith=DEMO_DOCUMENT_TITLE_PREFIX)
        .annotate(
            versions_count=Count("versions"),
            latest_version_number=Max("versions__version_number"),
        )
        .order_by("-updated_at", "id")
    )
    quizzes = GeneratedQuiz.objects.select_related(
        "from_version__document",
        "to_version__document",
    ).order_by("-created_at")[:8]
    attempts = QuizAttempt.objects.select_related("quiz").order_by("-created_at")[:8]

    return render(
        request,
        "demo/dashboard.html",
        {
            "documents": documents,
            "quizzes": quizzes,
            "attempts": attempts,
            "stats": {
                "documents_count": documents.count(),
                "quizzes_count": GeneratedQuiz.objects.count(),
                "attempts_count": QuizAttempt.objects.count(),
            },
        },
    )


@require_GET
def document_detail(request: HttpRequest, document_id: int) -> HttpResponse:
    document = _load_document_with_stats(document_id)
    versions = document.versions.order_by("version_number")
    suggested_pair = None
    if versions.count() >= 2:
        suggested_pair = (
            versions[versions.count() - 2],
            versions[versions.count() - 1],
        )

    return render(
        request,
        "demo/document_detail.html",
        {
            "document": document,
            "versions": versions,
            "suggested_pair": suggested_pair,
        },
    )


@require_http_methods(["GET", "POST"])
def compare_page(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        from_version_id = request.POST.get("from_version")
        to_version_id = request.POST.get("to_version")
        compare_url = reverse("demo-compare")
        return redirect(
            f"{compare_url}?from_version={from_version_id}"
            f"&to_version={to_version_id}"
        )

    from_version_id = request.GET.get("from_version")
    to_version_id = request.GET.get("to_version")

    if not from_version_id or not to_version_id:
        messages.error(request, "Выберите две версии одного документа для сравнения.")
        return redirect("demo-dashboard")

    from_version = get_object_or_404(
        DocumentVersion.objects.select_related("document").prefetch_related("chunks"),
        pk=from_version_id,
    )
    to_version = get_object_or_404(
        DocumentVersion.objects.select_related("document").prefetch_related("chunks"),
        pk=to_version_id,
    )

    if from_version.document_id != to_version.document_id:
        messages.error(request, "Сравнивать можно только версии одного документа.")
        return redirect("demo-dashboard")

    context = _build_compare_context(from_version=from_version, to_version=to_version)
    context.update(
        {
            "document": from_version.document,
            "from_version": from_version,
            "to_version": to_version,
        }
    )
    return render(request, "demo/compare.html", context)


@require_http_methods(["POST"])
def create_quiz(request: HttpRequest) -> HttpResponse:
    from_version = get_object_or_404(
        DocumentVersion, pk=request.POST.get("from_version")
    )
    to_version = get_object_or_404(DocumentVersion, pk=request.POST.get("to_version"))

    if from_version.document_id != to_version.document_id:
        messages.error(request, "Нельзя создать тест для версий из разных документов.")
        return redirect("demo-dashboard")

    try:
        limit = int(request.POST.get("limit", 5))
    except ValueError:
        limit = 5
    limit = min(max(limit, 1), 20)

    title = (request.POST.get("title") or "").strip()
    if not title:
        title = (
            f"Демо-тест: {from_version.document.title} "
            f"v{from_version.version_number} → v{to_version.version_number}"
        )

    diff_payload = build_version_diff(from_version=from_version, to_version=to_version)
    quiz_payload = build_quiz_from_diff(diff_payload, max_questions=limit)

    if quiz_payload["questions_count"] == 0:
        messages.error(request, "Для выбранной пары версий нет вопросов для теста.")
        compare_url = reverse("demo-compare")
        return redirect(
            f"{compare_url}?from_version={from_version.id}"
            f"&to_version={to_version.id}"
        )

    quiz = GeneratedQuiz.objects.create(
        from_version=from_version,
        to_version=to_version,
        title=title,
        payload=quiz_payload,
        questions_count=quiz_payload["questions_count"],
    )
    messages.success(request, "Тест создан. Теперь его можно утвердить.")
    return redirect("demo-quiz-detail", quiz_id=quiz.id)


@require_GET
def quizzes_page(request: HttpRequest) -> HttpResponse:
    quizzes = GeneratedQuiz.objects.select_related(
        "from_version__document",
        "to_version__document",
    ).order_by("-created_at")
    return render(request, "demo/quizzes.html", {"quizzes": quizzes})


@require_GET
def quiz_detail(request: HttpRequest, quiz_id: int) -> HttpResponse:
    quiz = get_object_or_404(
        GeneratedQuiz.objects.select_related(
            "from_version__document",
            "to_version__document",
        ),
        pk=quiz_id,
    )
    report = build_quiz_report_payload(quiz)
    return render(
        request,
        "demo/quiz_detail.html",
        {
            "quiz": quiz,
            "report": report,
        },
    )


@require_http_methods(["POST"])
def approve_quiz_view(request: HttpRequest, quiz_id: int) -> HttpResponse:
    quiz = get_object_or_404(GeneratedQuiz, pk=quiz_id)
    approved_by_name = (request.POST.get("approved_by_name") or "").strip()
    approval_comment = (request.POST.get("approval_comment") or "").strip()

    if not approved_by_name:
        messages.error(request, "Укажите ФИО ответственного лица.")
        return redirect("demo-quiz-detail", quiz_id=quiz.id)

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
    messages.success(request, "Тест утверждён и готов к выдаче сотруднику.")
    return redirect("demo-quiz-detail", quiz_id=quiz.id)


@require_http_methods(["GET", "POST"])
def take_quiz(request: HttpRequest, quiz_id: int) -> HttpResponse:
    quiz = get_object_or_404(GeneratedQuiz, pk=quiz_id)

    if quiz.status != GeneratedQuiz.Status.APPROVED:
        messages.error(request, "Перед прохождением тест нужно утвердить.")
        return redirect("demo-quiz-detail", quiz_id=quiz.id)

    questions = quiz.payload.get("questions", [])

    if request.method == "POST":
        participant_name = (request.POST.get("participant_name") or "").strip()
        submitted_answers: list[dict[str, Any]] = []

        for index, question in enumerate(questions):
            choice_index = request.POST.get(f"question_{index}")
            choice_text = ""
            if choice_index is not None:
                for choice in question.get("choices", []):
                    if str(choice.get("choice_index")) == str(choice_index):
                        choice_text = str(choice.get("text", ""))
                        break

            submitted_answers.append(
                {
                    "question_index": index,
                    "selected_choice_index": choice_index,
                    "selected_choice_text": choice_text,
                    "answer": choice_text,
                }
            )

        evaluation = evaluate_quiz_answers(
            quiz_payload=quiz.payload,
            submitted_answers=submitted_answers,
        )
        attempt = QuizAttempt.objects.create(
            quiz=quiz,
            participant_name=participant_name,
            answers=evaluation["results"],
            score=evaluation["score"],
            total_questions=evaluation["total_questions"],
            status=QuizAttempt.Status.COMPLETED,
            completed_at=timezone.now(),
        )
        messages.success(request, "Результат прохождения сохранён.")
        return redirect("demo-attempt-detail", attempt_id=attempt.id)

    return render(
        request,
        "demo/take_quiz.html",
        {
            "quiz": quiz,
            "questions": questions,
        },
    )


@require_GET
def attempt_detail(request: HttpRequest, attempt_id: int) -> HttpResponse:
    attempt = get_object_or_404(
        QuizAttempt.objects.select_related("quiz", "quiz__from_version__document"),
        pk=attempt_id,
    )
    percentage = 0.0
    if attempt.total_questions:
        percentage = round((attempt.score / attempt.total_questions) * 100, 2)

    return render(
        request,
        "demo/attempt_detail.html",
        {
            "attempt": attempt,
            "percentage": percentage,
        },
    )


@require_GET
def report_page(request: HttpRequest, quiz_id: int) -> HttpResponse:
    quiz = get_object_or_404(GeneratedQuiz, pk=quiz_id)
    report = build_quiz_report_payload(quiz)
    return render(
        request,
        "demo/report.html",
        {
            "quiz": quiz,
            "report": report,
        },
    )
