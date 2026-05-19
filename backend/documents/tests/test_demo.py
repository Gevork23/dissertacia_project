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
    GeneratedQuiz,
    Question,
    QuizAssignment,
    QuizAttempt,
)

TEST_MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class DemoViewsTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.admin_user = User.objects.get(username="admin")
        self.employee_user = User.objects.get(username="user")
        self.client.force_login(self.admin_user)

        self.document = Document.objects.create(
            title="Демо-регламент",
            description="Проверка demo UI",
        )
        self.version_one = self._make_version(
            version_number=1,
            filename="v1.txt",
            text=(
                "Раздел I Общие положения\n\n"
                "Статья 1 Срок\n"
                "1. Срок составляет 10 рабочих дней."
            ),
        )
        self.version_two = self._make_version(
            version_number=2,
            filename="v2.txt",
            text=(
                "Раздел I Общие положения\n\n"
                "Статья 1 Срок\n"
                "1. Срок составляет 7 рабочих дней."
            ),
        )
        self.quiz = GeneratedQuiz.objects.create(
            from_version=self.version_one,
            to_version=self.version_two,
            title="Демо-тест",
            questions_count=1,
            payload={
                "questions_count": 1,
                "questions": [
                    {
                        "question": "Какой срок установлен в новой редакции?",
                        "answer": "7 рабочих дней",
                        "choices": [
                            {
                                "choice_index": 0,
                                "text": "7 рабочих дней",
                                "is_correct": True,
                            },
                            {
                                "choice_index": 1,
                                "text": "10 рабочих дней",
                                "is_correct": False,
                            },
                        ],
                    }
                ],
            },
        )
        question = Question.objects.create(
            quiz=self.quiz,
            order=1,
            question_type=Question.QuestionType.SINGLE_CHOICE,
            prompt="Какой срок установлен в новой редакции?",
            correct_text_answer="7 рабочих дней",
        )
        Choice.objects.create(
            question=question,
            order=0,
            text="7 рабочих дней",
            is_correct=True,
        )
        Choice.objects.create(
            question=question,
            order=1,
            text="10 рабочих дней",
            is_correct=False,
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

    def _approve_quiz(self):
        self.quiz.status = GeneratedQuiz.Status.APPROVED
        self.quiz.approved_by_name = "Иванова Е.А."
        self.quiz.save(update_fields=["status", "approved_by_name", "updated_at"])

    def test_dashboard_is_available(self):
        response = self.client.get(reverse("demo-dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Демонстрационный контур защиты")
        self.assertContains(response, self.document.title)

    def test_compare_page_is_available(self):
        response = self.client.get(
            reverse("demo-compare"),
            {
                "from_version": self.version_one.id,
                "to_version": self.version_two.id,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Сравнение версий")
        self.assertContains(response, "Critical")
        self.assertContains(response, "Manual review")

    def test_visualize_page_is_available(self):
        response = self.client.get(
            reverse("demo-visualize"),
            {
                "from_version": self.version_one.id,
                "to_version": self.version_two.id,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Timeline")
        self.assertContains(response, 'id="severityChart"', html=False)
        self.assertContains(response, "Visualize")

    def test_quiz_can_be_submitted_for_review_and_approved_from_demo_ui(self):
        review_response = self.client.post(
            reverse("demo-submit-review-quiz", kwargs={"quiz_id": self.quiz.id})
        )
        self.assertEqual(review_response.status_code, 302)
        self.quiz.refresh_from_db()
        self.assertEqual(self.quiz.status, GeneratedQuiz.Status.PENDING_REVIEW)

        approve_response = self.client.post(
            reverse("demo-approve-quiz", kwargs={"quiz_id": self.quiz.id}),
            {"approved_by_name": "Иванова Е.А.", "approval_comment": "Согласовано."},
        )
        self.assertEqual(approve_response.status_code, 302)
        self.quiz.refresh_from_db()
        self.assertEqual(self.quiz.status, GeneratedQuiz.Status.APPROVED)
        self.assertEqual(self.quiz.approved_by_name, "Иванова Е.А.")

    def test_admin_can_take_approved_quiz_from_demo_ui(self):
        self._approve_quiz()

        start_response = self.client.post(
            reverse("demo-take-quiz", kwargs={"quiz_id": self.quiz.id}),
            {
                "action": "start",
                "participant_name": "Петров А.А.",
            },
        )

        self.assertEqual(start_response.status_code, 302)
        attempt = QuizAttempt.objects.get()
        self.assertEqual(attempt.status, QuizAttempt.Status.IN_PROGRESS)

        question = self.quiz.questions.get()
        correct_choice = question.choices.get(is_correct=True)
        submit_response = self.client.post(
            reverse("demo-take-quiz", kwargs={"quiz_id": self.quiz.id}),
            {
                "action": "submit",
                "attempt_id": attempt.id,
                f"question_{question.id}": str(correct_choice.id),
            },
        )

        self.assertEqual(submit_response.status_code, 302)
        attempt.refresh_from_db()
        self.assertEqual(attempt.score, 1)
        self.assertEqual(attempt.total_questions, 1)
        self.assertEqual(attempt.status, QuizAttempt.Status.COMPLETED)

    def test_employee_sees_only_assigned_quiz(self):
        self._approve_quiz()
        QuizAssignment.objects.create(
            quiz=self.quiz,
            user=self.employee_user,
            assigned_by=self.admin_user,
        )
        self.client.force_login(self.employee_user)

        response = self.client.get(reverse("demo-quizzes"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.quiz.title)

    def test_employee_cannot_open_unassigned_quiz(self):
        self._approve_quiz()
        self.client.force_login(self.employee_user)

        response = self.client.get(
            reverse("demo-quiz-detail", kwargs={"quiz_id": self.quiz.id})
        )

        self.assertEqual(response.status_code, 403)

    def test_employee_attempt_uses_account_name(self):
        self._approve_quiz()
        QuizAssignment.objects.create(
            quiz=self.quiz,
            user=self.employee_user,
            assigned_by=self.admin_user,
        )
        self.client.force_login(self.employee_user)

        response = self.client.post(
            reverse("demo-take-quiz", kwargs={"quiz_id": self.quiz.id}),
            {
                "action": "start",
                "participant_name": "Чужое имя",
            },
        )

        self.assertEqual(response.status_code, 302)
        attempt = QuizAttempt.objects.get()
        self.assertEqual(attempt.participant_name, self.employee_user.get_full_name())

    def test_admin_can_assign_approved_quiz(self):
        self._approve_quiz()

        response = self.client.post(
            reverse("demo-assign-quiz", kwargs={"quiz_id": self.quiz.id}),
            {"user_id": self.employee_user.id},
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            QuizAssignment.objects.filter(
                quiz=self.quiz,
                user=self.employee_user,
            ).exists()
        )
