from __future__ import annotations

import shutil
import tempfile
from io import BytesIO

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from docx import Document as DocxDocument
from pypdf import PdfWriter

from documents.models import Document, ManualDocument
from documents.services.manual_upload import extract_text_from_uploaded_file

TEST_MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class ManualUploadTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.admin_user = User.objects.get(username="admin")
        self.employee_user = User.objects.get(username="user")

    def make_txt_file(self, name: str = "law.txt", text: str = "Текст документа"):
        return SimpleUploadedFile(
            name=name,
            content=text.encode("utf-8"),
            content_type="text/plain",
        )

    def make_xml_file(self, name: str = "law.xml", text: str = "Текст XML"):
        payload = (
            "<act><meta><headingIPS>XML документ</headingIPS></meta>"
            f"<text><textIPS><p>{text}</p></textIPS></text></act>"
        )
        return SimpleUploadedFile(
            name=name,
            content=payload.encode("utf-8"),
            content_type="application/xml",
        )

    def make_docx_file(self, name: str = "law.docx"):
        buffer = BytesIO()
        document = DocxDocument()
        document.add_paragraph("Административный регламент")
        document.add_paragraph("Срок оказания услуги 5 дней.")
        document.save(buffer)
        return SimpleUploadedFile(
            name=name,
            content=buffer.getvalue(),
            content_type=(
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ),
        )

    def make_pdf_file(self, name: str = "law.pdf", text: str = "PDF text"):
        writer = PdfWriter()
        writer.add_blank_page(width=300, height=200)
        buffer = BytesIO()
        writer.write(buffer)
        # Reuse project's simple handcrafted PDF from upload tests would be overkill here;
        # pypdf blank page gives no text, so build a minimal text PDF stream manually.
        pdf_bytes = (
            b"%PDF-1.4\n"
            b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
            b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 400 400] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
            + f"4 0 obj\n<< /Length {len(text) + 29} >>\nstream\nBT\n/F1 12 Tf\n50 350 Td\n({text}) Tj\nET\nendstream\nendobj\n".encode(
                "latin-1"
            )
            + b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
            b"xref\n0 6\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n"
            b"0000000115 00000 n \n0000000241 00000 n \n0000000337 00000 n \n"
            b"trailer\n<< /Root 1 0 R /Size 6 >>\nstartxref\n407\n%%EOF\n"
        )
        return SimpleUploadedFile(
            name=name,
            content=pdf_bytes,
            content_type="application/pdf",
        )

    def test_manual_upload_requires_admin(self):
        self.client.force_login(self.employee_user)
        response = self.client.get(reverse("manual-upload"))
        self.assertEqual(response.status_code, 403)

    def test_documents_page_requires_admin(self):
        self.client.force_login(self.employee_user)
        response = self.client.get(reverse("manual-documents"))
        self.assertEqual(response.status_code, 403)

    def test_extract_text_from_uploaded_file_supports_txt_docx_pdf_xml(self):
        cases = [
            self.make_txt_file(text="Текст TXT"),
            self.make_docx_file(),
            self.make_pdf_file(text="PDF text"),
            self.make_xml_file(text="Текст XML"),
        ]

        results = [extract_text_from_uploaded_file(case) for case in cases]

        self.assertEqual(results[0].warning, "")
        self.assertIn("Текст TXT", results[0].text)
        self.assertEqual(results[1].warning, "")
        self.assertIn("Административный регламент", results[1].text)
        self.assertEqual(results[2].warning, "")
        self.assertIn("PDF text", results[2].text)
        self.assertEqual(results[3].warning, "")
        self.assertIn("Текст XML", results[3].text)

    def test_admin_can_upload_new_txt_document(self):
        self.client.force_login(self.admin_user)
        response = self.client.post(
            reverse("manual-upload"),
            {
                "title": "Новый регламент",
                "version": 1,
                "file": self.make_txt_file(text="Пункт 1. Новый текст."),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 302)
        document = Document.objects.get(title="Новый регламент")
        version = document.versions.get()
        manual = ManualDocument.objects.get(document=document)
        session = self.client.session

        self.assertEqual(version.version_number, 1)
        self.assertEqual(version.source_filename, "law.txt")
        self.assertEqual(manual.document_version_id, version.id)
        self.assertTrue(version.chunks.exists())
        self.assertTrue(session.get("rag_chunks"))
        self.assertEqual(session["rag_chunks"][0]["version_id"], version.id)

    def test_admin_can_upload_docx_and_pdf_documents(self):
        self.client.force_login(self.admin_user)
        cases = [
            ("DOCX регламент", self.make_docx_file(name="doc.docx")),
            ("PDF регламент", self.make_pdf_file(name="doc.pdf", text="PDF text")),
        ]

        for title, uploaded_file in cases:
            response = self.client.post(
                reverse("manual-upload"),
                {
                    "title": title,
                    "version": 1,
                    "file": uploaded_file,
                },
            )
            self.assertEqual(response.status_code, 302)

        self.assertTrue(Document.objects.filter(title="DOCX регламент").exists())
        self.assertTrue(Document.objects.filter(title="PDF регламент").exists())

    def test_admin_can_upload_new_versions_for_same_document(self):
        self.client.force_login(self.admin_user)
        first_response = self.client.post(
            reverse("manual-upload"),
            {
                "title": "Регламент версии",
                "version": 1,
                "file": self.make_txt_file(name="v1.txt", text="Редакция 1"),
            },
        )
        self.assertEqual(first_response.status_code, 302)
        document = Document.objects.get(title="Регламент версии")

        second_response = self.client.post(
            f"{reverse('manual-upload')}?document_id={document.id}",
            {
                "document_id": document.id,
                "title": document.title,
                "version": 2,
                "file": self.make_xml_file(name="v2.xml", text="Редакция 2"),
            },
        )

        self.assertEqual(second_response.status_code, 302)
        versions = list(document.versions.order_by("version_number"))
        self.assertEqual([item.version_number for item in versions], [1, 2])
        self.assertEqual(ManualDocument.objects.filter(document=document).count(), 2)
        session_versions = {
            chunk["version_number"] for chunk in self.client.session.get("rag_chunks", [])
        }
        self.assertEqual(session_versions, {1, 2})

    def test_documents_page_shows_compare_button_for_multi_version_document(self):
        self.client.force_login(self.admin_user)
        document = Document.objects.create(title="Документ для сравнения")
        self.client.post(
            reverse("manual-upload"),
            {
                "title": document.title,
                "document_id": document.id,
                "version": 1,
                "file": self.make_txt_file(name="v1.txt", text="Редакция 1"),
            },
        )
        self.client.post(
            f"{reverse('manual-upload')}?document_id={document.id}",
            {
                "title": document.title,
                "document_id": document.id,
                "version": 2,
                "file": self.make_txt_file(name="v2.txt", text="Редакция 2"),
            },
        )

        response = self.client.get(reverse("manual-documents"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Сравнить")
        self.assertContains(response, "Добавить версию")

    def test_admin_can_delete_single_version_and_document(self):
        self.client.force_login(self.admin_user)
        self.client.post(
            reverse("manual-upload"),
            {
                "title": "Документ на удаление",
                "version": 1,
                "file": self.make_txt_file(name="v1.txt", text="Редакция 1"),
            },
        )
        document = Document.objects.get(title="Документ на удаление")
        version = document.versions.get()

        response = self.client.post(reverse("manual-delete-version", args=[version.id]))

        self.assertEqual(response.status_code, 302)
        document.refresh_from_db()
        self.assertEqual(document.versions.count(), 0)
        self.assertIsNone(document.current_version)

        response = self.client.post(reverse("manual-delete-document", args=[document.id]))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Document.objects.filter(id=document.id).exists())
