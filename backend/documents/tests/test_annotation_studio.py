import shutil
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from ..domain.text_processing import sha256_hex
from ..models import (
    Document,
    DocumentVersion,
    GoldChangeAnnotation,
    GoldQuizAnnotation,
    GoldSummaryAnnotation,
)
from ..services.workflows import create_quiz_from_versions

TEST_MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class AnnotationStudioTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.admin_user = User.objects.get(username="admin")
        self.employee_user = User.objects.get(username="user")
        self.document = Document.objects.create(
            title="Annotation document",
            description="Annotation studio tests",
        )
        self.version_one = self._make_version(
            version_number=1,
            filename="ann_v1.txt",
            text=(
                "Раздел I Общие положения\n\n"
                "Статья 1 Срок\n"
                "1. Срок составляет 10 рабочих дней."
            ),
        )
        self.version_two = self._make_version(
            version_number=2,
            filename="ann_v2.txt",
            text=(
                "Раздел I Общие положения\n\n"
                "Статья 1 Срок\n"
                "1. Срок составляет 7 рабочих дней."
            ),
        )
        self.quiz = create_quiz_from_versions(
            from_version=self.version_one,
            to_version=self.version_two,
            title="Annotation quiz",
            max_questions=5,
        )
        self.comparison = self.quiz.comparison
        self.summary = self.quiz.summary
        self.change_item = self.comparison.change_items.order_by("sort_order", "id").first()
        self.question = self.quiz.questions.order_by("order", "id").first()

    def _make_version(self, *, version_number: int, filename: str, text: str):
        uploaded_file = SimpleUploadedFile(
            filename,
            text.encode("utf-8"),
            content_type="text/plain",
        )
        return DocumentVersion.objects.create(
            document=self.document,
            version_number=version_number,
            source_filename=filename,
            file=uploaded_file,
            extracted_text=text,
            normalized_text=text,
            content_hash=sha256_hex(text),
        )

    def test_models_can_be_created(self):
        change_annotation = GoldChangeAnnotation.objects.create(
            change_item=self.change_item,
            annotator=self.admin_user,
            corrected_semantic_type=self.change_item.semantic_type,
            corrected_significance_label=self.change_item.significance_label,
        )
        summary_annotation = GoldSummaryAnnotation.objects.create(
            summary=self.summary,
            source_change_item=self.change_item,
            annotator=self.admin_user,
            highlight_index=1,
            quality_label=GoldSummaryAnnotation.QualityLabel.GOOD,
        )
        quiz_annotation = GoldQuizAnnotation.objects.create(
            question=self.question,
            annotator=self.admin_user,
            quality_label=GoldQuizAnnotation.QualityLabel.GOOD,
        )

        self.assertIsNotNone(change_annotation.pk)
        self.assertIsNotNone(summary_annotation.pk)
        self.assertIsNotNone(quiz_annotation.pk)

    def test_annotations_dashboard_requires_admin_and_returns_200(self):
        self.client.force_login(self.employee_user)
        forbidden = self.client.get(reverse("demo-annotations-dashboard"))
        self.assertEqual(forbidden.status_code, 403)

        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("demo-annotations-dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Annotation Studio")

    def test_annotations_comparison_page_returns_200_for_admin(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(
            reverse(
                "demo-annotations-comparison",
                kwargs={"comparison_id": self.comparison.id},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"Comparison #{self.comparison.id}")

    def test_post_change_annotation_saves_corrected_fields(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse(
                "demo-annotations-comparison",
                kwargs={"comparison_id": self.comparison.id},
            ),
            {
                "action": "save_change",
                "change_item_id": self.change_item.id,
                "corrected_semantic_type": "deadline",
                "corrected_significance_label": "critical",
                "corrected_requires_manual_review": "true",
                "relevance": "relevant",
                "is_false_positive": "false",
                "comment": "Expert correction",
            },
        )

        self.assertEqual(response.status_code, 302)
        annotation = GoldChangeAnnotation.objects.get(
            change_item=self.change_item,
            annotator=self.admin_user,
        )
        self.assertEqual(annotation.corrected_semantic_type, "deadline")
        self.assertEqual(annotation.corrected_significance_label, "critical")
        self.assertTrue(annotation.corrected_requires_manual_review)
        self.assertEqual(annotation.comment, "Expert correction")

        second_response = self.client.post(
            reverse(
                "demo-annotations-comparison",
                kwargs={"comparison_id": self.comparison.id},
            ),
            {
                "action": "save_change",
                "change_item_id": self.change_item.id,
                "corrected_semantic_type": "deadline",
                "corrected_significance_label": "important",
                "corrected_requires_manual_review": "false",
                "relevance": "relevant",
                "is_false_positive": "false",
                "comment": "Updated expert correction",
            },
        )
        self.assertEqual(second_response.status_code, 302)
        self.assertEqual(
            GoldChangeAnnotation.objects.filter(
                change_item=self.change_item,
                annotator=self.admin_user,
            ).count(),
            1,
        )
        annotation.refresh_from_db()
        self.assertEqual(annotation.corrected_significance_label, "important")
        self.assertEqual(annotation.comment, "Updated expert correction")

    def test_post_summary_annotation_saves_quality_label(self):
        self.client.force_login(self.admin_user)
        first_highlight = (self.summary.highlights or [])[0]

        response = self.client.post(
            reverse(
                "demo-annotations-comparison",
                kwargs={"comparison_id": self.comparison.id},
            ),
            {
                "action": "save_summary",
                "summary_id": self.summary.id,
                "highlight_index": 1,
                "source_change_item_id": first_highlight.get("source_change_item_id"),
                "quality_label": "missing_key_point",
                "corrected_text": "Corrected highlight",
                "comment": "Missing important nuance",
            },
        )

        self.assertEqual(response.status_code, 302)
        annotation = GoldSummaryAnnotation.objects.get(
            summary=self.summary,
            annotator=self.admin_user,
            highlight_index=1,
        )
        self.assertEqual(annotation.quality_label, "missing_key_point")
        self.assertEqual(annotation.corrected_text, "Corrected highlight")

    def test_post_quiz_annotation_saves_quality_label(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse(
                "demo-annotations-comparison",
                kwargs={"comparison_id": self.comparison.id},
            ),
            {
                "action": "save_quiz",
                "question_id": self.question.id,
                "quality_label": "ambiguous",
                "corrected_question_text": "Corrected question text",
                "corrected_explanation": "Corrected explanation",
                "should_keep": "false",
                "comment": "Needs disambiguation",
            },
        )

        self.assertEqual(response.status_code, 302)
        annotation = GoldQuizAnnotation.objects.get(
            question=self.question,
            annotator=self.admin_user,
        )
        self.assertEqual(annotation.quality_label, "ambiguous")
        self.assertFalse(annotation.should_keep)
        self.assertEqual(annotation.corrected_question_text, "Corrected question text")

    def test_export_json_and_csv_return_payloads(self):
        GoldChangeAnnotation.objects.create(
            change_item=self.change_item,
            annotator=self.admin_user,
            corrected_semantic_type="deadline",
            corrected_significance_label="critical",
        )
        self.client.force_login(self.admin_user)

        json_response = self.client.get(reverse("demo-annotations-export-json"))
        csv_response = self.client.get(reverse("demo-annotations-export-csv"))

        self.assertEqual(json_response.status_code, 200)
        self.assertEqual(csv_response.status_code, 200)
        self.assertContains(json_response, "change_annotations")
        self.assertContains(csv_response, "annotation_type,object_id,comparison_id")
