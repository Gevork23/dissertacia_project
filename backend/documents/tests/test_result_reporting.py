import shutil
import tempfile
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from ..domain.text_processing import sha256_hex
from ..models import (
    Choice,
    Document,
    DocumentVersion,
    GeneratedQuiz,
    Question,
    QuizAttempt,
)
from ..services.llm_result_enhancer import ResultLLMEnhancementError
from ..services.result_reporting import (
    build_attempt_result_payload,
    build_quiz_report_payload,
)

TEST_MEDIA_ROOT = tempfile.mkdtemp()


class FakeResultLLMClient:
    def generate(self, *, system_prompt: str, user_prompt: str):
        if "краткий отчёт для руководителя" in system_prompt:
            text = "Группа сотрудников в среднем усвоила материал удовлетворительно; проблемной темой остаются сроки и порядок действий. Рекомендуется короткий повторный разбор и повторное тестирование."
            model = "fake-manager-model"
        elif "типовые ошибки" in system_prompt:
            text = "Типовые ошибки сгруппированы вокруг неверного понимания изменённого срока и связанного порядка действий. Именно этот блок документа сотрудники трактуют хуже всего."
            model = "fake-analysis-model"
        else:
            text = "Сотрудник справился частично: корректно распознал часть изменений, но ошибся в ключевой обновлённой норме. Рекомендуется повторно изучить проблемный фрагмент документа и пройти тест ещё раз."
            model = "fake-attempt-model"

        class Response:
            def __init__(self, text: str, model: str):
                self.text = text
                self.model = model

        return Response(text=text, model=model)


class FailingResultLLMClient:
    def generate(self, *, system_prompt: str, user_prompt: str):
        raise ResultLLMEnhancementError("Simulated LLM outage.")


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class ResultReportingAPITests(APITestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def _make_version(
        self, *, document: Document, version_number: int, filename: str, text: str
    ):
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

    def _build_quiz_with_two_questions(self) -> GeneratedQuiz:
        document = Document.objects.create(title="Phase 14 API")
        version_one = self._make_version(
            document=document,
            version_number=1,
            filename="phase14-v1.txt",
            text="Раздел 1. Старый срок — 10 дней. Раздел 2. Старый порядок.",
        )
        version_two = self._make_version(
            document=document,
            version_number=2,
            filename="phase14-v2.txt",
            text="Раздел 1. Новый срок — 7 дней. Раздел 2. Новый порядок.",
        )
        quiz = GeneratedQuiz.objects.create(
            from_version=version_one,
            to_version=version_two,
            title="Phase 14 Quiz",
            questions_count=2,
            status=GeneratedQuiz.Status.APPROVED,
            approved_by_name="Иванова Е.А.",
        )
        q1 = Question.objects.create(
            quiz=quiz,
            order=1,
            question_type=Question.QuestionType.SINGLE_CHOICE,
            prompt="Какой срок установлен в новой редакции?",
            explanation="Проверяется изменение срока.",
            correct_text_answer="7 дней",
        )
        Choice.objects.create(question=q1, order=0, text="7 дней", is_correct=True)
        Choice.objects.create(question=q1, order=1, text="10 дней", is_correct=False)
        q2 = Question.objects.create(
            quiz=quiz,
            order=2,
            question_type=Question.QuestionType.SINGLE_CHOICE,
            prompt="Каков новый порядок действий?",
            explanation="Проверяется изменение процедуры.",
            correct_text_answer="Новый порядок",
        )
        Choice.objects.create(
            question=q2, order=0, text="Новый порядок", is_correct=True
        )
        Choice.objects.create(
            question=q2, order=1, text="Старый порядок", is_correct=False
        )
        return quiz

    @override_settings(RESULT_LLM_ENABLED=True)
    @patch(
        "documents.services.result_reporting.get_default_result_llm_client",
        return_value=FakeResultLLMClient(),
    )
    def test_attempt_result_endpoint_returns_extended_payload(self, _client_factory):
        quiz = self._build_quiz_with_two_questions()

        start_response = self.client.post(
            reverse("start-quiz-attempt", kwargs={"quiz_id": quiz.id}),
            {"participant_name": "Петров А.А."},
            format="json",
        )
        self.assertEqual(start_response.status_code, status.HTTP_201_CREATED)
        attempt_id = start_response.data["attempt"]["id"]

        questions = list(
            quiz.questions.order_by("order", "id").prefetch_related("choices")
        )
        correct_choice = questions[0].choices.get(is_correct=True)
        wrong_choice = questions[1].choices.get(is_correct=False)

        submit_response = self.client.post(
            reverse("submit-quiz-attempt", kwargs={"quiz_id": quiz.id}),
            {
                "attempt_id": attempt_id,
                "answers": [
                    {
                        "question_id": questions[0].id,
                        "selected_choice_id": correct_choice.id,
                    },
                    {
                        "question_id": questions[1].id,
                        "selected_choice_id": wrong_choice.id,
                    },
                ],
            },
            format="json",
        )
        self.assertEqual(submit_response.status_code, status.HTTP_201_CREATED)
        self.assertIn("result", submit_response.data)
        self.assertIn("llm_feedback", submit_response.data["result"])

        result_response = self.client.get(
            reverse("attempt-result", kwargs={"attempt_id": attempt_id})
        )
        self.assertEqual(result_response.status_code, status.HTTP_200_OK)
        self.assertEqual(result_response.data["raw_score"], 1)
        self.assertEqual(result_response.data["wrong_answers"], 1)
        self.assertEqual(result_response.data["unanswered_questions"], 0)
        self.assertFalse(result_response.data["passed"])
        self.assertIn("llm_feedback", result_response.data)
        self.assertIn("llm_error_analysis", result_response.data)
        self.assertIn("llm_manager_summary", result_response.data)
        self.assertEqual(result_response.data["quiz_report"]["attempts_count"], 1)

    @override_settings(RESULT_LLM_ENABLED=True)
    @patch(
        "documents.services.result_reporting.get_default_result_llm_client",
        return_value=FakeResultLLMClient(),
    )
    def test_quiz_report_contains_llm_and_frequent_errors(self, _client_factory):
        quiz = self._build_quiz_with_two_questions()
        questions = list(
            quiz.questions.order_by("order", "id").prefetch_related("choices")
        )
        wrong_choice_q1 = questions[0].choices.get(is_correct=False)
        correct_choice_q2 = questions[1].choices.get(is_correct=True)

        for participant in ["Иванов И.И.", "Сидоров С.С."]:
            start_response = self.client.post(
                reverse("start-quiz-attempt", kwargs={"quiz_id": quiz.id}),
                {"participant_name": participant},
                format="json",
            )
            attempt_id = start_response.data["attempt"]["id"]
            submit_response = self.client.post(
                reverse("submit-quiz-attempt", kwargs={"quiz_id": quiz.id}),
                {
                    "attempt_id": attempt_id,
                    "answers": [
                        {
                            "question_id": questions[0].id,
                            "selected_choice_id": wrong_choice_q1.id,
                        },
                        {
                            "question_id": questions[1].id,
                            "selected_choice_id": correct_choice_q2.id,
                        },
                    ],
                },
                format="json",
            )
            self.assertEqual(submit_response.status_code, status.HTTP_201_CREATED)

        report_response = self.client.get(
            reverse("quiz-report", kwargs={"quiz_id": quiz.id})
        )
        self.assertEqual(report_response.status_code, status.HTTP_200_OK)
        self.assertEqual(report_response.data["attempts_count"], 2)
        self.assertTrue(report_response.data["frequent_errors"])
        self.assertIn("llm_error_analysis", report_response.data)
        self.assertIn("llm_manager_summary", report_response.data)
        self.assertEqual(report_response.data["pass_rate"], 0.0)


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class ResultReportingServiceAndDemoTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def _make_version(
        self, *, document: Document, version_number: int, filename: str, text: str
    ):
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

    def _build_completed_attempt(self) -> QuizAttempt:
        document = Document.objects.create(title="Phase 14 Service")
        version_one = self._make_version(
            document=document, version_number=1, filename="a1.txt", text="Старая версия"
        )
        version_two = self._make_version(
            document=document, version_number=2, filename="a2.txt", text="Новая версия"
        )
        quiz = GeneratedQuiz.objects.create(
            from_version=version_one,
            to_version=version_two,
            title="Service Quiz",
            questions_count=1,
            status=GeneratedQuiz.Status.APPROVED,
            approved_by_name="Иванова Е.А.",
        )
        question = Question.objects.create(
            quiz=quiz,
            order=1,
            question_type=Question.QuestionType.SINGLE_CHOICE,
            prompt="Какой срок теперь действует?",
            explanation="Проверяется срок.",
            correct_text_answer="7 дней",
        )
        correct_choice = Choice.objects.create(
            question=question, order=0, text="7 дней", is_correct=True
        )
        Choice.objects.create(
            question=question, order=1, text="10 дней", is_correct=False
        )
        attempt = QuizAttempt.objects.create(
            quiz=quiz,
            participant_name="Петров П.П.",
            answers=[
                {
                    "question_id": question.id,
                    "question_order": 1,
                    "question": question.prompt,
                    "question_explanation": question.explanation,
                    "selected_choice_id": correct_choice.id,
                    "submitted_answer": "7 дней",
                    "expected_answer": "7 дней",
                    "is_correct": True,
                    "answered": True,
                }
            ],
            score=1,
            total_questions=1,
            answered_questions=1,
            correct_answers=1,
            score_percent=100.0,
            status=QuizAttempt.Status.COMPLETED,
        )
        return attempt

    @override_settings(RESULT_LLM_ENABLED=True)
    @patch(
        "documents.services.result_reporting.get_default_result_llm_client",
        return_value=FakeResultLLMClient(),
    )
    def test_build_attempt_result_payload_and_quiz_report(self, _client_factory):
        attempt = self._build_completed_attempt()
        result_payload = build_attempt_result_payload(attempt)
        self.assertTrue(result_payload["passed"])
        self.assertEqual(result_payload["verdict"], "Отличное усвоение изменений")
        self.assertIn("llm_feedback", result_payload)

        report_payload = build_quiz_report_payload(attempt.quiz)
        attempt.refresh_from_db()
        attempt.quiz.refresh_from_db()
        self.assertEqual(report_payload["attempts_count"], 1)
        self.assertIn("llm_manager_summary", report_payload)
        self.assertEqual(attempt.llm_feedback_model, "fake-attempt-model")
        self.assertEqual(attempt.quiz.llm_reporting_model, "fake-analysis-model")

    @override_settings(RESULT_LLM_ENABLED=True)
    @patch(
        "documents.services.result_reporting.get_default_result_llm_client",
        return_value=FakeResultLLMClient(),
    )
    def test_demo_attempt_detail_renders_llm_sections(self, _client_factory):
        attempt = self._build_completed_attempt()
        self.client.force_login(User.objects.get(username="admin"))
        response = self.client.get(
            reverse("demo-attempt-detail", kwargs={"attempt_id": attempt.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "LLM-комментарий по результату")
        self.assertContains(response, "Краткий отчёт для руководителя")

    @override_settings(RESULT_LLM_ENABLED=False)
    @patch("documents.services.result_reporting.get_default_result_llm_client")
    def test_disabled_llm_is_normal_deterministic_mode(self, client_factory):
        attempt = self._build_completed_attempt()

        with self.assertLogs("documents.result_reporting", level="INFO") as captured:
            result_payload = build_attempt_result_payload(attempt)

        attempt.refresh_from_db()
        attempt.quiz.refresh_from_db()
        log_output = "\n".join(captured.output)

        client_factory.assert_not_called()
        self.assertTrue(result_payload["llm_feedback"])
        self.assertTrue(result_payload["llm_error_analysis"])
        self.assertTrue(result_payload["llm_manager_summary"])
        self.assertEqual(attempt.llm_feedback_model, "rule_based_fallback")
        self.assertEqual(attempt.quiz.llm_reporting_model, "rule_based_fallback")
        self.assertIn("LLM result enhancement is disabled", log_output)
        self.assertIn("deterministic fallback is used", log_output)
        self.assertNotIn("ERROR", log_output)
        self.assertNotIn("Traceback", log_output)
        self.assertNotIn("generation failed", log_output)

    @override_settings(RESULT_LLM_ENABLED=True)
    @patch(
        "documents.services.result_reporting.get_default_result_llm_client",
        return_value=FailingResultLLMClient(),
    )
    def test_enabled_llm_failure_falls_back_without_breaking_result(
        self, client_factory
    ):
        attempt = self._build_completed_attempt()

        with self.assertLogs("documents.result_reporting", level="WARNING") as captured:
            result_payload = build_attempt_result_payload(attempt)

        attempt.refresh_from_db()
        attempt.quiz.refresh_from_db()
        log_output = "\n".join(captured.output)

        self.assertTrue(client_factory.called)
        self.assertTrue(result_payload["llm_feedback"])
        self.assertTrue(result_payload["llm_error_analysis"])
        self.assertTrue(result_payload["llm_manager_summary"])
        self.assertEqual(result_payload["raw_score"], attempt.score)
        self.assertEqual(result_payload["score_percent"], attempt.score_percent)
        self.assertEqual(attempt.llm_feedback_model, "rule_based_fallback")
        self.assertEqual(attempt.quiz.llm_reporting_model, "rule_based_fallback")
        self.assertIn("deterministic fallback is used", log_output)
        self.assertIn("LLM result enhancement failed", log_output)
        self.assertIn("LLM quiz report enhancement failed", log_output)

    @override_settings(RESULT_LLM_ENABLED=False)
    @patch("documents.services.result_reporting.get_default_result_llm_client")
    def test_result_reporting_payload_remains_stable_without_llm(self, client_factory):
        attempt = self._build_completed_attempt()

        result_payload = build_attempt_result_payload(attempt)
        report_payload = build_quiz_report_payload(attempt.quiz)

        client_factory.assert_not_called()
        self.assertEqual(result_payload["raw_score"], 1)
        self.assertEqual(result_payload["score_percent"], 100.0)
        self.assertEqual(result_payload["correct_answers"], 1)
        self.assertTrue(result_payload["llm_feedback"])
        self.assertIn("quiz_report", result_payload)
        self.assertEqual(report_payload["attempts_count"], 1)
        self.assertTrue(report_payload["llm_error_analysis"])
        self.assertTrue(report_payload["llm_manager_summary"])
