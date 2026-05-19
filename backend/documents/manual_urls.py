from django.urls import path

from .manual_views import (
    delete_document,
    delete_version,
    manual_documents_page,
    upload_document,
)

urlpatterns = [
    path("", manual_documents_page, name="manual-documents"),
    path("upload/", upload_document, name="manual-upload"),
    path("<int:document_id>/delete/", delete_document, name="manual-delete-document"),
    path(
        "versions/<int:version_id>/delete/",
        delete_version,
        name="manual-delete-version",
    ),
]
