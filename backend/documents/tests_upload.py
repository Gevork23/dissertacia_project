import os
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Document, DocumentVersion

TEST_MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class DocumentUploadAPITests(APITestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def make_file(self, name: str, content: str, content_type: str = "text/plain"):
        return SimpleUploadedFile(
            name=name,
            content=content.encode("utf-8"),
            content_type=content_type,
        )

    def test_create_document_returns_phase4_ready_fields(self):
        response = self.client.post(
            reverse("documents-list"),
            {
                "title": "Приказ о приёме документов",
                "description": "Карточка документа без версий",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["title"], "Приказ о приёме документов")
        self.assertEqual(response.data["versions_count"], 0)
        self.assertIsNone(response.data["latest_version_number"])

    def test_upload_first_version_assigns_number_and_saves_file(self):
        document = Document.objects.create(title="Административный регламент")

        response = self.client.post(
            reverse("documents-versions", kwargs={"pk": document.id}),
            {
                "file": self.make_file("reglament_v1.txt", "Первая редакция"),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["document"], document.id)
        self.assertEqual(response.data["version_number"], 1)
        self.assertEqual(response.data["source_filename"], "reglament_v1.txt")
        self.assertEqual(response.data["file_size"], len("Первая редакция".encode("utf-8")))
        self.assertEqual(response.data["content_type"], "text/plain")

        version = DocumentVersion.objects.get(pk=response.data["id"])
        self.assertTrue(os.path.exists(version.file.path))
        self.assertIn(f"document_{document.id}", version.file.name)
        self.assertIn("version_1", version.file.name)

    def test_upload_next_version_auto_increments_number(self):
        document = Document.objects.create(title="Инструкция")
        DocumentVersion.objects.create(
            document=document,
            version_number=1,
            source_filename="instruction_v1.txt",
            file=self.make_file("instruction_v1.txt", "Редакция 1"),
            file_size=len("Редакция 1".encode("utf-8")),
            content_type="text/plain",
        )

        response = self.client.post(
            reverse("documents-versions", kwargs={"pk": document.id}),
            {
                "file": self.make_file("instruction_v2.txt", "Редакция 2"),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["version_number"], 2)
        self.assertEqual(document.versions.count(), 2)

    def test_versions_list_can_be_requested_for_specific_document(self):
        first_document = Document.objects.create(title="Документ 1")
        second_document = Document.objects.create(title="Документ 2")

        DocumentVersion.objects.create(
            document=first_document,
            version_number=1,
            source_filename="doc1_v1.txt",
            file=self.make_file("doc1_v1.txt", "Первая версия"),
            file_size=len("Первая версия".encode("utf-8")),
            content_type="text/plain",
        )
        DocumentVersion.objects.create(
            document=second_document,
            version_number=1,
            source_filename="doc2_v1.txt",
            file=self.make_file("doc2_v1.txt", "Другая версия"),
            file_size=len("Другая версия".encode("utf-8")),
            content_type="text/plain",
        )

        response = self.client.get(
            reverse("versions-list"),
            {"document": first_document.id},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["document"], first_document.id)
        self.assertEqual(response.data[0]["version_number"], 1)

    def test_document_list_contains_versions_count_and_latest_version_number(self):
        document = Document.objects.create(title="Положение")
        DocumentVersion.objects.create(
            document=document,
            version_number=1,
            source_filename="v1.txt",
            file=self.make_file("v1.txt", "Версия 1"),
            file_size=len("Версия 1".encode("utf-8")),
            content_type="text/plain",
        )
        DocumentVersion.objects.create(
            document=document,
            version_number=2,
            source_filename="v2.txt",
            file=self.make_file("v2.txt", "Версия 2"),
            file_size=len("Версия 2".encode("utf-8")),
            content_type="text/plain",
        )

        response = self.client.get(reverse("documents-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["versions_count"], 2)
        self.assertEqual(response.data[0]["latest_version_number"], 2)

    def test_upload_rejects_unsupported_extension(self):
        document = Document.objects.create(title="Плохой файл")

        response = self.client.post(
            reverse("documents-versions", kwargs={"pk": document.id}),
            {
                "file": self.make_file(
                    "malware.exe",
                    "not allowed",
                    content_type="application/octet-stream",
                ),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Unsupported file type", response.data["file"][0])