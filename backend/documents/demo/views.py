from __future__ import annotations

from typing import Any

from django.contrib import messages
from django.db.models import Count, Max
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from ..api.serializers import VersionDiffSerializer
from ..domain.change_enrichment import enrich_compare_payload
from ..domain.diff_quiz import build_quiz_from_diff
from ..domain.diff_summary import build_brief_summary
from ..models import Document, DocumentVersion, GeneratedQuiz, QuizAttempt
from ..services.exceptions import DomainWorkflowError
from ..services.quiz_attempts import (
    build_attempt_form_questions,
    get_quiz_attempt_block_reason,
    start_quiz_attempt,
    submit_started_quiz_attempt,
)
from ..services.quiz_workflow import (
    approve_generated_quiz,
    reject_generated_quiz,
    submit_quiz_for_review,
)
from ..services.result_reporting import (
    build_attempt_result_payload,
    build_quiz_report_payload,
)
from ..services.workflows import (
    EmptyQuizError,
    build_comparison_payload,
    create_quiz_from_versions,
)

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
    diff_payload = build_comparison_payload(
        from_version=from_version, to_version=to_version
    )
    serialized_diff = VersionDiffSerializer(diff_payload).data
    enriched_diff = enrich_compare_payload(serialized_diff)
    brief_payload = build_brief_summary(enriched_diff)
    quiz_preview = build_quiz_from_diff(enriched_diff, max_questions=10)

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

    if from_version.version_number >= to_version.version_number:
        messages.error(request, "Новая версия должна быть выбрана как целевая.")
        return redirect("demo-dashboard")

    try:
        context = _build_compare_context(
            from_version=from_version, to_version=to_version
        )
    except DomainWorkflowError as error:
        messages.error(request, str(error))
        return redirect("demo-dashboard")
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

    if from_version.version_number >= to_version.version_number:
        messages.error(request, "Новая версия должна быть выбрана как целевая.")
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

    try:
        quiz = create_quiz_from_versions(
            from_version=from_version,
            to_version=to_version,
            title=title,
            max_questions=limit,
        )
    except EmptyQuizError:
        messages.error(
            request,
            "Для выбранной пары версий нет достаточно значимых изменений для устойчивого теста.",
        )
        compare_url = reverse("demo-compare")
        return redirect(
            f"{compare_url}?from_version={from_version.id}"
            f"&to_version={to_version.id}"
        )
    messages.success(
        request, "Тест создан как черновик. Следующий шаг — отправка на проверку."
    )
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
def submit_quiz_review_view(request: HttpRequest, quiz_id: int) -> HttpResponse:
    quiz = get_object_or_404(GeneratedQuiz, pk=quiz_id)
    try:
        submit_quiz_for_review(quiz)
    except DomainWorkflowError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, "Тест передан на проверку ответственному лицу.")
    return redirect("demo-quiz-detail", quiz_id=quiz.id)


@require_http_methods(["POST"])
def approve_quiz_view(request: HttpRequest, quiz_id: int) -> HttpResponse:
    quiz = get_object_or_404(GeneratedQuiz, pk=quiz_id)
    approved_by_name = (request.POST.get("approved_by_name") or "").strip()
    approval_comment = (request.POST.get("approval_comment") or "").strip()

    try:
        approve_generated_quiz(
            quiz=quiz,
            approved_by_name=approved_by_name,
            approval_comment=approval_comment,
        )
    except DomainWorkflowError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, "Тест утверждён и готов к выдаче сотруднику.")
    return redirect("demo-quiz-detail", quiz_id=quiz.id)


@require_http_methods(["POST"])
def reject_quiz_view(request: HttpRequest, quiz_id: int) -> HttpResponse:
    quiz = get_object_or_404(GeneratedQuiz, pk=quiz_id)
    rejected_by_name = (request.POST.get("rejected_by_name") or "").strip()
    rejection_comment = (request.POST.get("rejection_comment") or "").strip()

    try:
        reject_generated_quiz(
            quiz=quiz,
            rejected_by_name=rejected_by_name,
            rejection_comment=rejection_comment,
        )
    except DomainWorkflowError as error:
        messages.error(request, str(error))
    else:
        messages.success(
            request,
            "Тест отклонён. Его можно переработать и повторно отправить на проверку.",
        )
    return redirect("demo-quiz-detail", quiz_id=quiz.id)


@require_http_methods(["GET", "POST"])
def take_quiz(request: HttpRequest, quiz_id: int) -> HttpResponse:
    quiz = get_object_or_404(GeneratedQuiz, pk=quiz_id)

    attempt_id = request.GET.get("attempt_id") or request.POST.get("attempt_id")
    current_attempt = None

    if attempt_id:
        current_attempt = get_object_or_404(
            QuizAttempt.objects.select_related("quiz"),
            pk=attempt_id,
            quiz=quiz,
        )

    if request.method == "POST":
        action = (request.POST.get("action") or "submit").strip()

        if action == "start":
            blocked_reason = get_quiz_attempt_block_reason(quiz)
            if blocked_reason is not None:
                messages.error(request, blocked_reason)
                return redirect("demo-quiz-detail", quiz_id=quiz.id)

            participant_name = (request.POST.get("participant_name") or "").strip()
            try:
                attempt, created = start_quiz_attempt(
                    quiz=quiz,
                    participant_name=participant_name,
                )
            except DomainWorkflowError as error:
                messages.error(request, str(error))
                return redirect("demo-take-quiz", quiz_id=quiz.id)

            if created:
                messages.success(
                    request, "Попытка прохождения начата. Можно отвечать на вопросы."
                )
            else:
                messages.info(
                    request, "Найдена уже начатая попытка. Продолжайте прохождение."
                )
            return redirect(
                f"{reverse('demo-take-quiz', kwargs={'quiz_id': quiz.id})}?attempt_id={attempt.id}"
            )

        if current_attempt is None:
            messages.error(request, "Попытка не найдена. Сначала начните прохождение.")
            return redirect("demo-take-quiz", quiz_id=quiz.id)

        questions = build_attempt_form_questions(quiz)
        submitted_answers: list[dict[str, Any]] = []

        for question in questions:
            choice_id = request.POST.get(f"question_{question['question_id']}")
            selected_choice_text = ""
            selected_choice_index = None

            if choice_id is not None:
                for choice in question.get("choices", []):
                    if str(choice.get("choice_id")) == str(choice_id):
                        selected_choice_text = str(choice.get("text", ""))
                        selected_choice_index = choice.get("choice_index")
                        break

            submitted_answers.append(
                {
                    "question_id": question["question_id"],
                    "question_index": question["question_index"],
                    "selected_choice_id": choice_id,
                    "selected_choice_index": selected_choice_index,
                    "selected_choice_text": selected_choice_text,
                    "answer": selected_choice_text,
                }
            )

        try:
            attempt, _ = submit_started_quiz_attempt(
                attempt=current_attempt,
                submitted_answers=submitted_answers,
            )
        except DomainWorkflowError as error:
            messages.error(request, str(error))
            return redirect(
                f"{reverse('demo-take-quiz', kwargs={'quiz_id': quiz.id})}?attempt_id={current_attempt.id}"
            )

        messages.success(request, "Результат прохождения сохранён.")
        return redirect("demo-attempt-detail", attempt_id=attempt.id)

    blocked_reason = None
    if current_attempt is None:
        blocked_reason = get_quiz_attempt_block_reason(quiz)
        if blocked_reason is not None:
            messages.error(request, blocked_reason)
            return redirect("demo-quiz-detail", quiz_id=quiz.id)

    questions = build_attempt_form_questions(quiz)
    return render(
        request,
        "demo/take_quiz.html",
        {
            "quiz": quiz,
            "questions": questions,
            "attempt": current_attempt,
        },
    )


@require_GET
def attempt_detail(request: HttpRequest, attempt_id: int) -> HttpResponse:
    attempt = get_object_or_404(
        QuizAttempt.objects.select_related("quiz", "quiz__from_version__document"),
        pk=attempt_id,
    )

    try:
        result = build_attempt_result_payload(attempt)
    except DomainWorkflowError as error:
        messages.error(request, str(error))
        return redirect("demo-quiz-detail", quiz_id=attempt.quiz_id)

    return render(
        request,
        "demo/attempt_detail.html",
        {
            "attempt": attempt,
            "result": result,
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
