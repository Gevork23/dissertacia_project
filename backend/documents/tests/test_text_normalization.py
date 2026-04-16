from __future__ import annotations

from django.test import SimpleTestCase

from ..domain.text_processing import (
    PDF_PAGE_BREAK,
    normalize_document_text,
    normalize_text,
)


class DocumentTextNormalizationTests(SimpleTestCase):
    def test_normalize_text_preserves_numero_sign(self):
        raw_text = "Приказ № 3\r\n\u00a0от 17.12.2024"

        normalized = normalize_text(raw_text)

        self.assertEqual(normalized, "Приказ № 3\nот 17.12.2024")
        self.assertNotIn("No 3", normalized)

    def test_normalize_document_text_for_pdf_removes_page_noise(self):
        extracted_text = (
            "HEADER\n"
            "1\n"
            "Статья 1\n"
            "В организации устанавлива-\n"
            "ется порядок работы\n"
            f"{PDF_PAGE_BREAK}"
            "HEADER\n"
            "2\n"
            "1.1. Работник обязан соблюдать регламент,\n"
            "а также требования безопасности.\n"
            "[SIGNERSTAMP1]"
        )

        normalized = normalize_document_text(extracted_text, extension=".pdf")
        normalized_lines = [line for line in normalized.splitlines() if line.strip()]

        self.assertNotIn("HEADER", normalized)
        self.assertNotIn("[SIGNERSTAMP1]", normalized)
        self.assertNotIn("1", normalized_lines)
        self.assertNotIn("2", normalized_lines)
        self.assertIn("В организации устанавливается порядок работы", normalized)
        self.assertIn(
            "1.1. Работник обязан соблюдать регламент, "
            "а также требования безопасности.",
            normalized,
        )

    def test_normalize_document_text_for_pdf_preserves_legal_structure(self):
        extracted_text = (
            "Статья 1\n"
            "1.1. Обязанности работника\n"
            "1.2. Права работника\n"
            "а) соблюдать регламент"
        )

        normalized = normalize_document_text(extracted_text, extension=".pdf")

        self.assertEqual(
            normalized,
            "Статья 1\n1.1. Обязанности работника\n"
            "1.2. Права работника\nа) соблюдать регламент",
        )
