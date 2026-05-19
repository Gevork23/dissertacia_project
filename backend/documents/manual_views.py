from __future__ import annotations

from typing import Any

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Max
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from accounts.permissions import admin_required

from .models import Document, DocumentVersion, ManualDocument
from .services.ingestion import (
    DuplicateDocumentVersionError,
    InvalidDocumentVersionFileError,
)
from .services.manual_upload import (
    extract_text_from_uploaded_file,
    refresh_manual_rag_chunks,
)
from .services.versioning import create_uploaded_document_version


def _document_queryset():
    return (
        Document.objects.annotate(
            versions_count=Count("versions"),
            latest_version_number=Max("versions__version_number"),
        )
        .prefetch_related("versions")
        .order_by("-updated_at", "-created_at")
    )


def _refresh_document_current_version(document: Document) -> None:
    latest_version = document.versions.order_by("-version_number", "-created_at").first()
    document.current_version = latest_version
    document.save(update_fields=["current_version", "updated_at"])


@require_GET
@admin_required
def manual_documents_page(request: HttpRequest) -> HttpResponse:
    document_rows: list[dict[str, Any]] = []
    for document in _document_queryset():
        ordered_versions = list(document.versions.order_by("version_number"))
        compare_url = ""
        if len(ordered_versions) >= 2:
            compare_url = (
                f"{reverse('demo-compare')}?from_version={ordered_versions[-2].id}"
                f"&to_version={ordered_versions[-1].id}"
            )
        document_rows.append(
            {
                "document": document,
                "compare_url": compare_url,
                "detail_url": reverse("demo-document-detail", args=[document.id]),
                "add_version_url": f"{reverse('manual-upload')}?document_id={document.id}",
            }
        )

    upload_log = ManualDocument.objects.select_related(
        "uploaded_by",
        "document",
        "document_version",
    )[:20]
    return render(
        request,
        "manual_upload/documents.html",
        {
            "document_rows": document_rows,
            "upload_log": upload_log,
        },
    )


@require_http_methods(["POST"])
@admin_required
@transaction.atomic
def delete_document(request: HttpRequest, document_id: int) -> HttpResponse:
    document = get_object_or_404(Document, pk=document_id)
    title = document.title
    document.delete()
    request.session.pop("rag_chunks", None)
    request.session.modified = True
    messages.success(request, f"Документ удалён: {title}.")
    return redirect("manual-documents")


@require_http_methods(["POST"])
@admin_required
@transaction.atomic
def delete_version(request: HttpRequest, version_id: int) -> HttpResponse:
    version = get_object_or_404(
        DocumentVersion.objects.select_related("document"),
        pk=version_id,
    )
    document = version.document
    label = f"{document.title} v{version.version_number}"
    version.delete()
    _refresh_document_current_version(document)
    refresh_manual_rag_chunks(request, document=document)
    messages.success(request, f"Версия удалена: {label}.")
    return redirect("demo-document-detail", document_id=document.id)


@require_http_methods(["GET", "POST"])
@admin_required
def upload_document(request: HttpRequest) -> HttpResponse:
    document_id = request.GET.get("document_id") or request.POST.get("document_id")
    existing_document = None
    if document_id:
        existing_document = get_object_or_404(Document, pk=document_id)

    if request.method == "POST":
        title = " ".join((request.POST.get("title") or "").split())
        uploaded_file = request.FILES.get("file")
        target = (
            f"{request.path}?document_id={existing_document.id}"
            if existing_document is not None
            else request.path
        )

        if existing_document is None and not title:
            messages.error(request, "Укажите название документа.")
            return redirect(target)

        if uploaded_file is None:
            messages.error(request, "Выберите файл для загрузки.")
            return redirect(target)

        extraction = extract_text_from_uploaded_file(uploaded_file)
        if extraction.warning:
            messages.error(request, extraction.warning)
            return redirect(target)

        document = existing_document or Document.objects.create(title=title)

        try:
            version = create_uploaded_document_version(
                document=document,
                uploaded_file=uploaded_file,
                source_filename=getattr(uploaded_file, "name", ""),
            )
        except (
            InvalidDocumentVersionFileError,
            DuplicateDocumentVersionError,
            ValidationError,
            ValueError,
        ) as error:
            if existing_document is None and not document.versions.exists():
                document.delete()
            messages.error(request, str(error))
            return redirect(target)

        ManualDocument.objects.create(
            title=document.title,
            uploaded_by=request.user,
            file=version.file,
            extracted_text=version.extracted_text,
            version=version.version_number,
            document=document,
            document_version=version,
        )
        refresh_manual_rag_chunks(request, document=document)
        messages.success(
            request,
            f"Документ загружен: {document.title} v{version.version_number}.",
        )
        return redirect("manual-documents")

    next_version = 1
    if existing_document is not None:
        current = existing_document.versions.order_by("-version_number").first()
        if current is not None:
            next_version = current.version_number + 1

    return render(
        request,
        "manual_upload/upload.html",
        {
            "existing_document": existing_document,
            "next_version": next_version,
            "prefill_title": existing_document.title if existing_document else "",
            "back_url": reverse("manual-documents"),
        },
    )
