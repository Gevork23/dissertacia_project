import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from ..domain.diff import build_version_diff
from ..domain.diff_quiz import build_quiz_from_diff
from ..domain.diff_summary import build_brief_summary
from ..domain.text_processing import sha256_hex
from ..models import Chunk, Document, DocumentVersion
from ..services.workflows import create_quiz_from_versions, materialize_comparison

TEST_MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class SignificancePipelineTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def make_version(
        self,
        *,
        document: Document,
        version_number: int,
        text: str,
        filename: str,
    ) -> DocumentVersion:
        uploaded_file = SimpleUploadedFile(
            filename,
            text.encode("utf-8"),
            content_type="text/plain",
        )
        return DocumentVersion.objects.create(
            document=document,
            version_number=version_number,
            source_filename=filename,
            file=uploaded_file,
            extracted_text=text,
            normalized_text=text,
            content_hash=sha256_hex(text),
        )

    def make_chunk(
        self,
        *,
        version: DocumentVersion,
        chunk_index: int,
        heading: str,
        section_path: str,
        text: str,
    ) -> Chunk:
        return Chunk.objects.create(
            version=version,
            chunk_index=chunk_index,
            heading=heading,
            section_path=section_path,
            text=text,
            text_hash=sha256_hex(text),
        )

    def setUp(self):
        self.document = Document.objects.create(
            title="Значимость изменений",
            description="Проверка Phase 9",
        )
        self.version_one = self.make_version(
            document=self.document,
            version_number=1,
            text=(
                "Статья 1 Срок\n"
                "Срок рассмотрения заявления составляет 10 рабочих дней.\n\n"
                "Статья 2 Общие положения\n"
                "Прием документов осуществляется ежедневно."
            ),
            filename="v1.txt",
        )
        self.version_two = self.make_version(
            document=self.document,
            version_number=2,
            text=(
                "Статья 1 Срок\n"
                "Срок рассмотрения заявления составляет 5 рабочих дней.\n\n"
                "Статья 2 Общие положения\n"
                "Приём документов осуществляется ежедневно."
            ),
            filename="v2.txt",
        )

        self.make_chunk(
            version=self.version_one,
            chunk_index=1,
            heading="Статья 1 · Срок",
            section_path="Статья 1",
            text="Срок рассмотрения заявления составляет 10 рабочих дней.",
        )
        self.make_chunk(
            version=self.version_one,
            chunk_index=2,
            heading="Статья 2 · Общие положения",
            section_path="Статья 2",
            text="Прием документов осуществляется ежедневно.",
        )
        self.make_chunk(
            version=self.version_two,
            chunk_index=1,
            heading="Статья 1 · Срок",
            section_path="Статья 1",
            text="Срок рассмотрения заявления составляет 5 рабочих дней.",
        )
        self.make_chunk(
            version=self.version_two,
            chunk_index=2,
            heading="Статья 2 · Общие положения",
            section_path="Статья 2",
            text="Приём документов осуществляется ежедневно.",
        )

    def test_materialized_change_items_store_significance_fields(self):
        comparison, summary, _, change_items = materialize_comparison(
            from_version=self.version_one,
            to_version=self.version_two,
        )

        self.assertEqual(comparison.change_items.count(), 2)
        self.assertEqual(len(change_items), 2)

        deadline_item = comparison.change_items.get(semantic_type="deadline")
        editorial_item = comparison.change_items.get(semantic_type="editorial")

        self.assertEqual(deadline_item.significance_label, "critical")
        self.assertGreaterEqual(deadline_item.significance_score, 0.9)
        self.assertFalse(deadline_item.requires_manual_review)
        self.assertTrue(deadline_item.significance_rules)
        self.assertTrue(deadline_item.significance_reason)

        self.assertEqual(editorial_item.significance_label, "editorial")
        self.assertFalse(editorial_item.requires_manual_review)
        self.assertEqual(summary.highlights[0]["significance_label"], "critical")
        self.assertEqual(summary.highlights[0]["semantic_type"], "deadline")

    def test_brief_summary_prioritizes_non_editorial_highlights(self):
        diff_payload = build_version_diff(self.version_one, self.version_two)

        brief_payload = build_brief_summary(diff_payload)

        self.assertEqual(brief_payload["summary"]["by_significance"]["critical"], 1)
        self.assertEqual(brief_payload["summary"]["by_significance"]["editorial"], 1)
        self.assertEqual(
            brief_payload["highlights"][0]["significance_label"], "critical"
        )
        self.assertEqual(brief_payload["highlights"][0]["semantic_type"], "deadline")

    def test_quiz_prefers_significant_changes_over_editorial(self):
        diff_payload = build_version_diff(self.version_one, self.version_two)

        quiz_payload = build_quiz_from_diff(diff_payload, max_questions=1)

        self.assertEqual(quiz_payload["questions_count"], 1)
        self.assertEqual(quiz_payload["questions"][0]["significance_label"], "critical")
        self.assertEqual(quiz_payload["questions"][0]["semantic_type"], "deadline")

    def test_saved_quiz_links_question_to_prioritized_change_item(self):
        quiz = create_quiz_from_versions(
            from_version=self.version_one,
            to_version=self.version_two,
            title="Квиз по значимым изменениям",
            max_questions=1,
        )

        question = quiz.questions.get()
        self.assertIsNotNone(question.source_change_item)
        self.assertEqual(question.source_change_item.semantic_type, "deadline")
        self.assertEqual(question.source_change_item.significance_label, "critical")
        self.assertIn("ключевые условия", question.explanation)
