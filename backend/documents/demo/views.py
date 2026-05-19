from __future__ import annotations

import json
from typing import Any

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Max
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from accounts.permissions import admin_required, get_user_display_name, is_admin

from ..api.serializers import VersionDiffSerializer
from ..domain.change_enrichment import enrich_compare_payload
from ..domain.diff_quiz import build_quiz_from_diff
from ..domain.diff_summary import build_brief_summary
from ..models import (
    Document,
    DocumentVersion,
    GeneratedQuiz,
    ModeratedChange,
    QuizAssignment,
    QuizAttempt,
)
from ..research_dashboard import build_research_dashboard_context, resolve_artifact_path
from ..services.exceptions import DomainWorkflowError
from ..services.moderation import (
    MODERATION_LABEL_OPTIONS,
    annotate_diff_for_moderation,
    moderation_stats,
    normalize_moderation_label,
)
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

VISUAL_LABELS = ("critical", "important", "minor")

DEMO_DOCUMENT_TITLE_PREFIX = "DEMO МФЦ:"


def _get_visible_quizzes_queryset(user):
    queryset = GeneratedQuiz.objects.select_related(
        "from_version__document",
        "to_version__document",
    )
    if is_admin(user):
        return queryset
    return queryset.filter(assignments__user=user).distinct()


def _employee_users_queryset():
    return (
        User.objects.select_related("profile")
        .filter(is_active=True, profile__role="employee")
        .order_by("username")
    )


def _ensure_quiz_access(request: HttpRequest, quiz: GeneratedQuiz) -> None:
    if is_admin(request.user):
        return
    if not quiz.assignments.filter(user=request.user).exists():
        raise PermissionDenied("This quiz is not assigned to the current employee.")


def _ensure_attempt_access(request: HttpRequest, attempt: QuizAttempt) -> None:
    if is_admin(request.user):
        return
    if not attempt.quiz.assignments.filter(user=request.user).exists():
        raise PermissionDenied("This attempt is not available for the current employee.")
    allowed_names = {request.user.username, get_user_display_name(request.user)}
    if attempt.participant_name not in allowed_names:
        raise PermissionDenied("Employees can view only their own attempts.")


def _load_document_with_stats(document_id: int) -> Document:
    return get_object_or_404(
        Document.objects.annotate(
            versions_count=Count("versions"),
            latest_version_number=Max("versions__version_number"),
        ),
        pk=document_id,
    )


def _documents_with_version_choices() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    documents = (
        Document.objects.annotate(
            versions_count=Count("versions"),
            latest_version_number=Max("versions__version_number"),
        )
        .prefetch_related("versions")
        .order_by("-updated_at", "-created_at")
    )
    for document in documents:
        versions = list(document.versions.order_by("version_number"))
        rows.append(
            {
                "document": document,
                "versions": versions,
                "has_pair": len(versions) >= 2,
            }
        )
    return rows


def _build_compare_context(
    *,
    from_version: DocumentVersion,
    to_version: DocumentVersion,
    use_moderation: bool = False,
) -> dict[str, Any]:
    diff_payload = build_comparison_payload(
        from_version=from_version, to_version=to_version
    )
    serialized_diff = VersionDiffSerializer(diff_payload).data
    enriched_diff = enrich_compare_payload(serialized_diff)
    moderation_rows: list[dict[str, Any]] = []
    moderation_summary = {"total": 0, "moderated": 0, "automatic": 0}
    if use_moderation:
        enriched_diff, moderation_rows = annotate_diff_for_moderation(
            enriched_diff,
            from_version=from_version,
            to_version=to_version,
            apply_corrections=True,
        )
        moderation_summary = moderation_stats(moderation_rows)
    brief_payload = build_brief_summary(enriched_diff)
    quiz_preview = build_quiz_from_diff(enriched_diff, max_questions=10)

    return {
        "diff": enriched_diff,
        "brief": brief_payload,
        "quiz_preview": quiz_preview,
        "moderation_rows": moderation_rows,
        "moderation_summary": moderation_summary,
    }


def _to_minor_label(label: str) -> str:
    normalized = str(label or "").strip().lower()
    if normalized in {"critical", "important"}:
        return normalized
    return "minor"


def _truncate_tooltip_text(text: str, limit: int = 220) -> str:
    normalized = " ".join(str(text or "").split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "..."


def _build_visualization_context(diff: dict[str, Any]) -> dict[str, Any]:
    timeline_items: list[dict[str, Any]] = []
    severity_counts = {label: 0 for label in VISUAL_LABELS}

    def append_item(
        *,
        change_type: str,
        payload: dict[str, Any],
        old_text: str,
        new_text: str,
        title: str,
    ) -> None:
        raw_label = payload.get("significance_label", "not_evaluated")
        visual_label = _to_minor_label(raw_label)
        severity_counts[visual_label] += 1
        timeline_items.append(
            {
                "index": len(timeline_items) + 1,
                "change_type": change_type,
                "label": visual_label,
                "raw_label": raw_label,
                "semantic_type": payload.get("semantic_type", "unclassified"),
                "title": title,
                "old_text": _truncate_tooltip_text(old_text),
                "new_text": _truncate_tooltip_text(new_text),
                "requires_manual_review": bool(
                    payload.get("requires_manual_review", False)
                ),
            }
        )

    for item in diff.get("modified", []):
        to_chunk = item.get("to_chunk") or {}
        from_chunk = item.get("from_chunk") or {}
        append_item(
            change_type="modified",
            payload=item,
            old_text=from_chunk.get("text", ""),
            new_text=to_chunk.get("text", ""),
            title=to_chunk.get("heading")
            or to_chunk.get("section_path")
            or "Modified chunk",
        )

    for item in diff.get("added", []):
        append_item(
            change_type="added",
            payload=item,
            old_text="",
            new_text=item.get("text", ""),
            title=item.get("heading") or item.get("section_path") or "Added chunk",
        )

    for item in diff.get("removed", []):
        append_item(
            change_type="removed",
            payload=item,
            old_text=item.get("text", ""),
            new_text="",
            title=item.get("heading") or item.get("section_path") or "Removed chunk",
        )

    for item in diff.get("moved", []):
        to_chunk = item.get("to_chunk") or {}
        from_chunk = item.get("from_chunk") or {}
        append_item(
            change_type="moved",
            payload=item,
            old_text=from_chunk.get("text", ""),
            new_text=to_chunk.get("text", ""),
            title=to_chunk.get("heading")
            or to_chunk.get("section_path")
            or "Moved chunk",
        )

    return {
        "visual_summary": {
            "critical": severity_counts["critical"],
            "important": severity_counts["important"],
            "minor": severity_counts["minor"],
            "total": len(timeline_items),
        },
        "timeline_items": timeline_items,
    }


def _serialize_rag_chunks(*, version: DocumentVersion) -> list[dict[str, Any]]:
    serialized: list[dict[str, Any]] = []
    version_label = f"v{version.version_number}"
    for chunk in version.chunks.order_by("chunk_index"):
        serialized.append(
            {
                "chunk_id": f"{version.id}:{chunk.id or chunk.chunk_index}",
                "document_id": version.document_id,
                "document_title": version.document.title,
                "version_id": version.id,
                "version_number": version.version_number,
                "version_label": version_label,
                "heading": chunk.heading,
                "section_path": chunk.section_path,
                "text": chunk.text,
                "fragment_type": chunk.fragment_type,
                "chunk_index": chunk.chunk_index,
            }
        )
    return serialized


def _store_rag_chunks(
    request: HttpRequest,
    *,
    from_version: DocumentVersion,
    to_version: DocumentVersion,
) -> None:
    if not request.session.session_key:
        request.session.save()
    request.session["rag_chunks"] = [
        *_serialize_rag_chunks(version=from_version),
        *_serialize_rag_chunks(version=to_version),
    ]
    request.session.modified = True


def _resolve_version_pair(
    *,
    request: HttpRequest,
    from_version_id: str | None,
    to_version_id: str | None,
    missing_message: str,
) -> tuple[DocumentVersion | None, DocumentVersion | None, HttpResponse | None]:
    if not from_version_id or not to_version_id:
        messages.error(request, missing_message)
        return None, None, None

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
        return None, None, redirect("demo-dashboard")

    if from_version.version_number >= to_version.version_number:
        messages.error(request, "Новая версия должна быть выбрана как целевая.")
        return None, None, redirect("demo-dashboard")

    return from_version, to_version, None


@require_GET
@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    documents = (
        Document.objects.filter(title__startswith=DEMO_DOCUMENT_TITLE_PREFIX)
        .annotate(
            versions_count=Count("versions"),
            latest_version_number=Max("versions__version_number"),
        )
        .order_by("-updated_at", "id")
    )
    quizzes = _get_visible_quizzes_queryset(request.user).order_by("-created_at")[:8]
    attempts_queryset = QuizAttempt.objects.select_related("quiz")
    if is_admin(request.user):
        attempts = attempts_queryset.order_by("-created_at")[:8]
        attempts_count = QuizAttempt.objects.count()
        quizzes_count = GeneratedQuiz.objects.count()
    else:
        attempts = (
            attempts_queryset.filter(
                quiz__assignments__user=request.user,
                participant_name__in=[
                    get_user_display_name(request.user),
                    request.user.username,
                ],
            )
            .distinct()
            .order_by("-created_at")[:8]
        )
        attempts_count = attempts.count()
        quizzes_count = _get_visible_quizzes_queryset(request.user).count()

    return render(
        request,
        "demo/dashboard.html",
        {
            "documents": documents,
            "quizzes": quizzes,
            "attempts": attempts,
            "stats": {
                "documents_count": documents.count(),
                "quizzes_count": quizzes_count,
                "attempts_count": attempts_count,
            },
        },
    )


@require_GET
@login_required
def research_dashboard_page(request: HttpRequest) -> HttpResponse:
    context = build_research_dashboard_context()
    return render(request, "demo/research_dashboard.html", context)


@require_GET
@login_required
def research_artifact_view(request: HttpRequest, artifact_path: str) -> HttpResponse:
    resolved = resolve_artifact_path(artifact_path)
    if resolved is None:
        raise Http404("Artifact not available.")
    return FileResponse(resolved.open("rb"))


@require_GET
@admin_required
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
            "delete_document_url": reverse("manual-delete-document", args=[document.id]),
        },
    )


@require_http_methods(["GET", "POST"])
@admin_required
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
    from_version, to_version, failure_response = _resolve_version_pair(
        request=request,
        from_version_id=from_version_id,
        to_version_id=to_version_id,
        missing_message="Выберите две версии одного документа для сравнения.",
    )
    if failure_response is not None:
        return failure_response
    if from_version is None or to_version is None:
        return redirect("demo-dashboard")

    try:
        context = _build_compare_context(
            from_version=from_version, to_version=to_version
        )
    except DomainWorkflowError as error:
        messages.error(request, str(error))
        return redirect("demo-dashboard")
    _, moderation_rows = annotate_diff_for_moderation(
        context["diff"],
        from_version=from_version,
        to_version=to_version,
        apply_corrections=False,
    )
    _store_rag_chunks(
        request,
        from_version=from_version,
        to_version=to_version,
    )
    context.update(
        {
            "document": from_version.document,
            "from_version": from_version,
            "to_version": to_version,
            "moderation_summary": moderation_stats(moderation_rows),
        }
    )
    return render(request, "demo/compare.html", context)


@require_GET
@admin_required
def visualize_page(request: HttpRequest) -> HttpResponse:
    from_version_id = request.GET.get("from_version")
    to_version_id = request.GET.get("to_version")
    from_version, to_version, failure_response = _resolve_version_pair(
        request=request,
        from_version_id=from_version_id,
        to_version_id=to_version_id,
        missing_message="Выберите две версии одного документа для визуализации.",
    )
    if failure_response is not None:
        return failure_response
    if from_version is None or to_version is None:
        return redirect("demo-dashboard")

    try:
        context = _build_compare_context(
            from_version=from_version,
            to_version=to_version,
        )
    except DomainWorkflowError as error:
        messages.error(request, str(error))
        return redirect("demo-dashboard")

    _store_rag_chunks(
        request,
        from_version=from_version,
        to_version=to_version,
    )
    _, moderation_rows = annotate_diff_for_moderation(
        context["diff"],
        from_version=from_version,
        to_version=to_version,
        apply_corrections=False,
    )
    context.update(_build_visualization_context(context["diff"]))
    context.update(
        {
            "document": from_version.document,
            "from_version": from_version,
            "to_version": to_version,
            "moderation_summary": moderation_stats(moderation_rows),
        }
    )
    return render(request, "demo/visualize.html", context)


@require_GET
@admin_required
def moderate_page(request: HttpRequest) -> HttpResponse:
    from_version_id = request.GET.get("from_version")
    to_version_id = request.GET.get("to_version")

    if not from_version_id or not to_version_id:
        selected_document_id = request.GET.get("document_id") or ""
        selected_document = None
        selected_versions: list[DocumentVersion] = []
        if selected_document_id:
            try:
                selected_document = Document.objects.get(pk=selected_document_id)
                selected_versions = list(
                    selected_document.versions.order_by("version_number")
                )
            except Document.DoesNotExist:
                selected_document = None
                selected_versions = []
        return render(
            request,
            "demo/moderate.html",
            {
                "document": None,
                "from_version": None,
                "to_version": None,
                "moderation_rows": [],
                "moderation_summary": {"total": 0, "moderated": 0, "automatic": 0},
                "moderation_label_options": MODERATION_LABEL_OPTIONS,
                "document_rows": _documents_with_version_choices(),
                "selected_document": selected_document,
                "selected_versions": selected_versions,
            },
        )

    from_version, to_version, failure_response = _resolve_version_pair(
        request=request,
        from_version_id=from_version_id,
        to_version_id=to_version_id,
        missing_message="Выберите две версии одного документа для модерации.",
    )
    if failure_response is not None:
        return failure_response
    if from_version is None or to_version is None:
        return redirect("demo-dashboard")

    try:
        context = _build_compare_context(
            from_version=from_version,
            to_version=to_version,
            use_moderation=False,
        )
    except DomainWorkflowError as error:
        messages.error(request, str(error))
        return redirect("demo-dashboard")

    _, moderation_rows = annotate_diff_for_moderation(
        context["diff"],
        from_version=from_version,
        to_version=to_version,
        apply_corrections=False,
    )
    context.update(
        {
            "document": from_version.document,
            "from_version": from_version,
            "to_version": to_version,
            "moderation_rows": moderation_rows,
            "moderation_summary": moderation_stats(moderation_rows),
            "moderation_label_options": MODERATION_LABEL_OPTIONS,
        }
    )
    return render(request, "demo/moderate.html", context)


@require_http_methods(["POST"])
@admin_required
def moderate_api(request: HttpRequest) -> HttpResponse:
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return HttpResponse(
            json.dumps({"status": "error", "detail": "Invalid JSON."}),
            content_type="application/json",
            status=400,
        )

    from_version_id = payload.get("from_version")
    to_version_id = payload.get("to_version")
    changes = payload.get("changes") or []
    if not isinstance(changes, list):
        return HttpResponse(
            json.dumps({"status": "error", "detail": "Field 'changes' must be a list."}),
            content_type="application/json",
            status=400,
        )

    from_version = get_object_or_404(
        DocumentVersion.objects.select_related("document").prefetch_related("chunks"),
        pk=from_version_id,
    )
    to_version = get_object_or_404(
        DocumentVersion.objects.select_related("document").prefetch_related("chunks"),
        pk=to_version_id,
    )

    if from_version.document_id != to_version.document_id:
        return HttpResponse(
            json.dumps(
                {"status": "error", "detail": "Versions must belong to the same document."}
            ),
            content_type="application/json",
            status=400,
        )
    if from_version.version_number >= to_version.version_number:
        return HttpResponse(
            json.dumps(
                {"status": "error", "detail": "Target version must be newer than source version."}
            ),
            content_type="application/json",
            status=400,
        )

    diff_payload = build_comparison_payload(
        from_version=from_version,
        to_version=to_version,
    )
    serialized_diff = VersionDiffSerializer(diff_payload).data
    enriched_diff = enrich_compare_payload(serialized_diff)
    _, moderation_rows = annotate_diff_for_moderation(
        enriched_diff,
        from_version=from_version,
        to_version=to_version,
        apply_corrections=False,
    )
    valid_changes = {row["change_id"]: row for row in moderation_rows}

    saved = 0
    for item in changes:
        if not isinstance(item, dict):
            continue
        change_id = str(item.get("change_id") or "").strip()
        if not change_id or change_id not in valid_changes:
            continue
        corrected_label = normalize_moderation_label(item.get("corrected_label"))
        comment = str(item.get("comment") or "").strip()
        row = valid_changes[change_id]
        ModeratedChange.objects.update_or_create(
            from_version=from_version,
            to_version=to_version,
            change_id=change_id,
            defaults={
                "original_label": row["original_label"],
                "corrected_label": corrected_label,
                "comment": comment,
                "moderated_by": request.user,
            },
        )
        saved += 1

    return HttpResponse(
        json.dumps({"status": "ok", "saved": saved}),
        content_type="application/json",
        status=200,
    )


@require_http_methods(["POST"])
@admin_required
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
    use_moderation = request.POST.get("use_moderation") == "on"

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
            use_moderation=use_moderation,
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
@login_required
def quizzes_page(request: HttpRequest) -> HttpResponse:
    quizzes = _get_visible_quizzes_queryset(request.user).order_by("-created_at")
    return render(request, "demo/quizzes.html", {"quizzes": quizzes})


@require_GET
@login_required
def quiz_detail(request: HttpRequest, quiz_id: int) -> HttpResponse:
    quiz = get_object_or_404(
        GeneratedQuiz.objects.select_related(
            "from_version__document",
            "to_version__document",
        ),
        pk=quiz_id,
    )
    _ensure_quiz_access(request, quiz)
    report = build_quiz_report_payload(quiz)
    return render(
        request,
        "demo/quiz_detail.html",
        {
            "quiz": quiz,
            "report": report,
            "employee_users": _employee_users_queryset() if is_admin(request.user) else [],
            "assigned_user_ids": set(quiz.assignments.values_list("user_id", flat=True)),
            "is_admin": is_admin(request.user),
        },
    )


@require_http_methods(["POST"])
@admin_required
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
@admin_required
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
@admin_required
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
@login_required
def take_quiz(request: HttpRequest, quiz_id: int) -> HttpResponse:
    quiz = get_object_or_404(GeneratedQuiz, pk=quiz_id)
    _ensure_quiz_access(request, quiz)

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
            if not is_admin(request.user):
                participant_name = get_user_display_name(request.user)
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
@login_required
def attempt_detail(request: HttpRequest, attempt_id: int) -> HttpResponse:
    attempt = get_object_or_404(
        QuizAttempt.objects.select_related("quiz", "quiz__from_version__document"),
        pk=attempt_id,
    )

    _ensure_attempt_access(request, attempt)
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
@login_required
def report_page(request: HttpRequest, quiz_id: int) -> HttpResponse:
    quiz = get_object_or_404(GeneratedQuiz, pk=quiz_id)
    _ensure_quiz_access(request, quiz)
    report = build_quiz_report_payload(quiz)
    return render(
        request,
        "demo/report.html",
        {
            "quiz": quiz,
            "report": report,
        },
    )


@require_http_methods(["POST"])
@admin_required
def assign_quiz_view(request: HttpRequest, quiz_id: int) -> HttpResponse:
    quiz = get_object_or_404(GeneratedQuiz, pk=quiz_id)
    assignee = get_object_or_404(
        User.objects.select_related("profile"),
        pk=request.POST.get("user_id"),
        profile__role="employee",
    )
    QuizAssignment.objects.get_or_create(
        quiz=quiz,
        user=assignee,
        defaults={"assigned_by": request.user},
    )
    messages.success(request, f"Тест назначен пользователю {assignee.username}.")
    return redirect("demo-quiz-detail", quiz_id=quiz.id)
