import shutil
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from ..domain.text_processing import sha256_hex
from ..models import (
    Choice,
    Document,
    DocumentVersion,
    Employee,
    GeneratedQuiz,
    QuizAssignment,
)
from ..services.quiz_attempts import start_quiz_attempt, submit_started_quiz_attempt
from ..services.workflows import create_quiz_from_versions, materialize_comparison
from ..traceability import build_comparison_trace, calculate_trace_completeness

TEST_MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class TraceabilityTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.admin_user = User.objects.get(username="admin")
        self.employee_user = User.objects.get(username="user")
        self.employee = Employee.objects.create(
            full_name=self.employee_user.get_full_name() or self.employee_user.username
        )
        self.document = Document.objects.create(
            title="Trace document",
            description="Traceability tests",
        )
        self.version_one = self._make_version(
            version_number=1,
            filename="trace_v1.txt",
            text=(
                "Раздел I Общие положения\n\n"
                "Статья 1 Срок\n"
                "1. Срок составляет 10 рабочих дней."
            ),
        )
        self.version_two = self._make_version(
            version_number=2,
            filename="trace_v2.txt",
            text=(
                "Раздел I Общие положения\n\n"
                "Статья 1 Срок\n"
                "1. Срок составляет 7 рабочих дней."
            ),
        )

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

    def test_build_comparison_trace_returns_structure(self):
        comparison, summary, _diff, _items = materialize_comparison(
            from_version=self.version_one,
            to_version=self.version_two,
        )

        trace = build_comparison_trace(comparison)

        self.assertEqual(trace["comparison"].id, comparison.id)
        self.assertEqual(trace["trace_summary"]["total_changes"], len(trace["trace_items"]))
        self.assertGreaterEqual(len(trace["trace_items"]), 1)
        self.assertIs(summary.comparison, comparison)

    def test_trace_completeness_counts_missing_links(self):
        summary = calculate_trace_completeness(
            [
                {"summary_links": [1], "quiz_links": [1], "attempt_links": [1], "trace_status": "complete"},
                {"summary_links": [], "quiz_links": [], "attempt_links": [], "trace_status": "missing_summary_link"},
            ]
        )

        self.assertEqual(summary["total_changes"], 2)
        self.assertEqual(summary["changes_with_summary_link"], 1)
        self.assertEqual(summary["changes_with_quiz_link"], 1)
        self.assertEqual(summary["changes_with_attempts"], 1)
        self.assertEqual(summary["complete_traces"], 1)
        self.assertEqual(summary["partial_traces"], 1)

    def test_traceability_page_shows_missing_link_warnings(self):
        self.client.force_login(self.admin_user)
        comparison, _summary, _diff, _items = materialize_comparison(
            from_version=self.version_one,
            to_version=self.version_two,
        )

        response = self.client.get(
            reverse("demo-traceability", kwargs={"comparison_id": comparison.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No linked quiz question found.")
        self.assertContains(response, "No attempt result available.")

    def test_traceability_page_shows_quiz_question_and_attempt(self):
        self.client.force_login(self.admin_user)
        quiz = create_quiz_from_versions(
            from_version=self.version_one,
            to_version=self.version_two,
            title="Trace quiz",
            max_questions=5,
        )
        quiz.status = GeneratedQuiz.Status.APPROVED
        quiz.approved_by_name = "Admin"
        quiz.save(update_fields=["status", "approved_by_name", "updated_at"])

        question = quiz.questions.order_by("order", "id").first()
        self.assertIsNotNone(question)
        correct_choice = question.choices.get(is_correct=True)

        attempt, _created = start_quiz_attempt(
            quiz=quiz,
            participant_name=self.employee_user.get_full_name() or self.employee_user.username,
            employee=self.employee,
        )
        submit_started_quiz_attempt(
            attempt=attempt,
            submitted_answers=[
                {
                    "question_id": question.id,
                    "selected_choice_id": correct_choice.id,
                }
            ],
        )

        response = self.client.get(
            reverse("demo-traceability", kwargs={"comparison_id": quiz.comparison_id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"Question #{question.id}")
        self.assertContains(response, f"Attempt #{attempt.id}")
        self.assertContains(response, correct_choice.text)

    def test_traceability_page_requires_admin_access(self):
        quiz = create_quiz_from_versions(
            from_version=self.version_one,
            to_version=self.version_two,
            title="Access quiz",
            max_questions=5,
        )
        QuizAssignment.objects.create(
            quiz=quiz,
            user=self.employee_user,
            assigned_by=self.admin_user,
        )
        self.client.force_login(self.employee_user)

        response = self.client.get(
            reverse("demo-traceability", kwargs={"comparison_id": quiz.comparison_id})
        )

        self.assertEqual(response.status_code, 403)

    def test_quiz_detail_shows_traceability_link_for_admin(self):
        self.client.force_login(self.admin_user)
        quiz = create_quiz_from_versions(
            from_version=self.version_one,
            to_version=self.version_two,
            title="Linked quiz",
            max_questions=5,
        )

        response = self.client.get(
            reverse("demo-quiz-detail", kwargs={"quiz_id": quiz.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse("demo-traceability", kwargs={"comparison_id": quiz.comparison_id}),
        )
