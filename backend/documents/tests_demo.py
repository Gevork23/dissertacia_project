import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Document, DocumentVersion, GeneratedQuiz, QuizAttempt
from .text_processing import sha256_hex

TEST_MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class DemoViewsTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
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

    def test_approved_quiz_can_be_taken_from_demo_ui(self):
        self.quiz.status = GeneratedQuiz.Status.APPROVED
        self.quiz.approved_by_name = "Иванова Е.А."
        self.quiz.save(update_fields=["status", "approved_by_name", "updated_at"])

        response = self.client.post(
            reverse("demo-take-quiz", kwargs={"quiz_id": self.quiz.id}),
            {
                "participant_name": "Петров А.А.",
                "question_0": "0",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(QuizAttempt.objects.count(), 1)
        attempt = QuizAttempt.objects.get()
        self.assertEqual(attempt.score, 1)
        self.assertEqual(attempt.total_questions, 1)
