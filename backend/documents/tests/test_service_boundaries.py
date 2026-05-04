import shutil
import tempfile
from unittest.mock import Mock, patch, sentinel

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings

from ..domain.text_processing import sha256_hex
from ..models import Document, DocumentVersion, GeneratedQuiz, QuizAttempt
from ..services import workflows
from ..services.exceptions import DomainWorkflowError
from ..services.quiz_attempts import start_quiz_attempt
from ..services.result_reporting import build_attempt_result_payload

TEST_MEDIA_ROOT = tempfile.mkdtemp()


class WorkflowCompatibilityBoundaryTests(SimpleTestCase):
    def test_attempt_wrappers_delegate_to_quiz_attempt_service(self):
        with patch.object(
            workflows.quiz_attempt_services,
            "start_quiz_attempt",
            return_value=(sentinel.attempt, True),
        ) as start_service:
            result = workflows.start_quiz_attempt(
                quiz=sentinel.quiz,
                participant_name="Петров А.А.",
                employee=sentinel.employee,
            )
        self.assertEqual(result, (sentinel.attempt, True))
        start_service.assert_called_once_with(
            quiz=sentinel.quiz,
            participant_name="Петров А.А.",
            employee=sentinel.employee,
        )

        with patch.object(
            workflows.quiz_attempt_services,
            "submit_started_quiz_attempt",
            return_value=(sentinel.attempt, {"score": 1}),
        ) as submit_service:
            result = workflows.submit_started_quiz_attempt(
                attempt=sentinel.attempt,
                submitted_answers=[{"question_id": 1}],
            )
        self.assertEqual(result, (sentinel.attempt, {"score": 1}))
        submit_service.assert_called_once_with(
            attempt=sentinel.attempt,
            submitted_answers=[{"question_id": 1}],
        )

    def test_quiz_lifecycle_wrappers_delegate_to_quiz_workflow_service(self):
        quiz = Mock()
        with patch.object(
            workflows.quiz_workflow_services,
            "approve_generated_quiz",
            return_value=quiz,
        ) as approve_service:
            result = workflows.approve_generated_quiz(
                quiz=quiz,
                approved_by_name="Иванова Е.А.",
                approval_comment="Согласовано.",
            )
        self.assertIs(result, quiz)
        approve_service.assert_called_once_with(
            quiz=quiz,
            approved_by_name="Иванова Е.А.",
            approval_comment="Согласовано.",
        )

        with patch.object(
            workflows.quiz_workflow_services,
            "mark_quiz_superseded",
            return_value=quiz,
        ) as supersede_service:
            result = workflows.mark_quiz_superseded(quiz, reason="Newer quiz")
        self.assertIs(result, quiz)
        supersede_service.assert_called_once_with(quiz, reason="Newer quiz")


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class ServiceBoundaryPersistenceTests(TestCase):
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

    def make_quiz(self, *, questions_count: int = 1) -> GeneratedQuiz:
        document = Document.objects.create(title="Service boundary quiz")
        version_one = self.make_version(
            document=document,
            version_number=1,
            filename="boundary-v1.txt",
            text="Старая редакция.",
        )
        version_two = self.make_version(
            document=document,
            version_number=2,
            filename="boundary-v2.txt",
            text="Новая редакция.",
        )
        return GeneratedQuiz.objects.create(
            from_version=version_one,
            to_version=version_two,
            title="Boundary Quiz",
            questions_count=questions_count,
            status=GeneratedQuiz.Status.APPROVED,
            approved_by_name="Иванова Е.А.",
        )

    def test_start_attempt_rejects_empty_quiz_in_attempt_service(self):
        quiz = self.make_quiz(questions_count=0)

        with self.assertRaisesMessage(
            DomainWorkflowError,
            "Cannot submit an attempt for an empty quiz.",
        ):
            start_quiz_attempt(quiz=quiz, participant_name="Петров А.А.")

    def test_result_reporting_uses_attempt_snapshot_without_rescoring_answers(self):
        quiz = self.make_quiz(questions_count=1)
        attempt = QuizAttempt.objects.create(
            quiz=quiz,
            participant_name="Петров А.А.",
            total_questions=1,
            answered_questions=1,
            correct_answers=0,
            score=0,
            score_percent=0.0,
            status=QuizAttempt.Status.COMPLETED,
            answers=[
                {
                    "question_id": 1,
                    "question": "Что изменилось?",
                    "answered": True,
                    "is_correct": True,
                    "submitted_answer": "Ответ выглядит верным, но snapshot решающий.",
                    "expected_answer": "Эталон",
                }
            ],
        )

        payload = build_attempt_result_payload(attempt, ensure_llm=False)

        self.assertEqual(payload["raw_score"], 0)
        self.assertEqual(payload["correct_answers"], 0)
        self.assertEqual(payload["score_percent"], 0.0)
        self.assertFalse(payload["passed"])
