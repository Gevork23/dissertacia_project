import shutil
import tempfile
from unittest.mock import Mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .analysis_service import (
    analyze_chunk_entities,
    analyze_version_entities,
    extract_entities_by_mode,
)
from .change_types import ChangeType
from .diff import build_version_diff
from .entity_extraction import extract_entities_from_text
from .entity_schema import EntityType, ExtractionMethod
from .models import Chunk, ChunkAnalysis, Document, DocumentVersion, GeneratedQuiz
from .text_processing import sha256_hex

TEST_MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class CompareVersionsAPITests(APITestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def make_version(
        self,
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

    def test_compare_versions_requires_query_params(self):
        url = reverse("compare-versions")

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["detail"],
            "Query parameters 'from_version' and 'to_version' are required.",
        )

    def test_compare_versions_rejects_versions_from_different_documents(self):
        doc_one = Document.objects.create(title="Документ 1", description="")
        doc_two = Document.objects.create(title="Документ 2", description="")

        version_one = self.make_version(
            document=doc_one,
            version_number=1,
            text="Текст первой версии",
            filename="v1.txt",
        )
        version_two = self.make_version(
            document=doc_two,
            version_number=1,
            text="Текст второй версии",
            filename="v2.txt",
        )

        url = reverse("compare-versions")
        response = self.client.get(
            url,
            {
                "from_version": version_one.id,
                "to_version": version_two.id,
            },
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["detail"],
            "Versions must belong to the same document.",
        )

    def test_compare_versions_returns_expected_chunk_diff(self):
        document = Document.objects.create(
            title="Локальный акт",
            description="Проверка diff",
        )

        version_one = self.make_version(
            document=document,
            version_number=1,
            text=(
                "Глава 1\n"
                "Старый текст главы 1\n\n"
                "Глава 2\n"
                "Текст, который будет удалён"
            ),
            filename="v1.txt",
        )
        version_two = self.make_version(
            document=document,
            version_number=2,
            text=(
                "Глава 1\n" "Новый текст главы 1\n\n" "Глава 3\n" "Совсем новый текст"
            ),
            filename="v2.txt",
        )

        unchanged_text = "Общее содержимое без изменений"
        modified_old_text = "Старый текст раздела про порядок согласования"
        modified_new_text = "Новый текст раздела про порядок согласования"
        removed_text = "Этот фрагмент удалили"
        added_text = "Этот фрагмент добавили"

        self.make_chunk(
            version=version_one,
            chunk_index=1,
            heading="Глава 1",
            section_path="Глава 1",
            text=unchanged_text,
        )
        self.make_chunk(
            version=version_one,
            chunk_index=2,
            heading="Глава 2",
            section_path="Глава 2",
            text=modified_old_text,
        )
        self.make_chunk(
            version=version_one,
            chunk_index=3,
            heading="Приложение",
            section_path="Приложение",
            text=removed_text,
        )

        self.make_chunk(
            version=version_two,
            chunk_index=1,
            heading="Глава 1",
            section_path="Глава 1",
            text=unchanged_text,
        )
        self.make_chunk(
            version=version_two,
            chunk_index=2,
            heading="Глава 2",
            section_path="Глава 2",
            text=modified_new_text,
        )
        self.make_chunk(
            version=version_two,
            chunk_index=3,
            heading="Глава 3",
            section_path="Глава 3",
            text=added_text,
        )

        url = reverse("compare-versions")
        response = self.client.get(
            url,
            {
                "from_version": version_one.id,
                "to_version": version_two.id,
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["from_version"]["id"], version_one.id)
        self.assertEqual(response.data["to_version"]["id"], version_two.id)
        self.assertFalse(response.data["identical"])

        self.assertEqual(response.data["summary"]["added"], 1)
        self.assertEqual(response.data["summary"]["removed"], 1)
        self.assertEqual(response.data["summary"]["modified"], 1)
        self.assertEqual(response.data["summary"]["moved"], 0)
        self.assertEqual(response.data["summary"]["unchanged"], 1)
        self.assertIn("by_type", response.data["summary"])

        self.assertEqual(len(response.data["added"]), 1)
        self.assertEqual(response.data["added"][0]["heading"], "Глава 3")
        self.assertEqual(response.data["added"][0]["text"], added_text)

        self.assertEqual(len(response.data["removed"]), 1)
        self.assertEqual(response.data["removed"][0]["heading"], "Приложение")
        self.assertEqual(response.data["removed"][0]["text"], removed_text)

        self.assertEqual(len(response.data["modified"]), 1)
        self.assertEqual(
            response.data["modified"][0]["from_chunk"]["heading"],
            "Глава 2",
        )
        self.assertEqual(
            response.data["modified"][0]["from_chunk"]["text"],
            modified_old_text,
        )
        self.assertEqual(
            response.data["modified"][0]["to_chunk"]["heading"],
            "Глава 2",
        )
        self.assertEqual(
            response.data["modified"][0]["to_chunk"]["text"],
            modified_new_text,
        )
        self.assertEqual(
            response.data["modified"][0]["match_reason"],
            "section_path",
        )
        self.assertGreater(response.data["modified"][0]["similarity"], 0.5)

        self.assertEqual(response.data["moved"], [])
        self.assertIn("--- from_version", response.data["text_diff"])
        self.assertIn("+++ to_version", response.data["text_diff"])

    def test_compare_versions_detects_moved_chunk(self):
        document = Document.objects.create(
            title="Перемещение раздела",
            description="",
        )

        version_one = self.make_version(
            document=document,
            version_number=1,
            text="Первая версия текста",
            filename="move1.txt",
        )
        version_two = self.make_version(
            document=document,
            version_number=2,
            text="Вторая версия текста",
            filename="move2.txt",
        )

        moved_text = "Одинаковый раздел, который просто переехал"
        stable_text = "Стабильный раздел без изменений"

        self.make_chunk(
            version=version_one,
            chunk_index=1,
            heading="Раздел 1",
            section_path="Раздел 1",
            text=moved_text,
        )
        self.make_chunk(
            version=version_one,
            chunk_index=2,
            heading="Раздел 2",
            section_path="Раздел 2",
            text=stable_text,
        )

        self.make_chunk(
            version=version_two,
            chunk_index=1,
            heading="Раздел 2",
            section_path="Раздел 2",
            text=stable_text,
        )
        self.make_chunk(
            version=version_two,
            chunk_index=2,
            heading="Раздел 1",
            section_path="Раздел 1",
            text=moved_text,
        )

        url = reverse("compare-versions")
        response = self.client.get(
            url,
            {
                "from_version": version_one.id,
                "to_version": version_two.id,
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["identical"])
        self.assertEqual(response.data["summary"]["added"], 0)
        self.assertEqual(response.data["summary"]["removed"], 0)
        self.assertEqual(response.data["summary"]["modified"], 0)
        self.assertEqual(response.data["summary"]["moved"], 2)
        self.assertEqual(response.data["summary"]["unchanged"], 0)
        self.assertIn("by_type", response.data["summary"])
        self.assertEqual(
            response.data["summary"]["by_type"][ChangeType.STRUCTURAL.value],
            2,
        )
        self.assertEqual(len(response.data["moved"]), 2)
        self.assertEqual(response.data["added"], [])
        self.assertEqual(response.data["removed"], [])
        self.assertEqual(response.data["modified"], [])

    def test_compare_versions_returns_identical_diff_for_same_content(self):
        document = Document.objects.create(
            title="Одинаковые версии",
            description="",
        )

        version_one = self.make_version(
            document=document,
            version_number=1,
            text="Одинаковый текст документа",
            filename="same1.txt",
        )
        version_two = self.make_version(
            document=document,
            version_number=2,
            text="Одинаковый текст документа",
            filename="same2.txt",
        )

        self.make_chunk(
            version=version_one,
            chunk_index=1,
            heading="Раздел 1",
            section_path="Раздел 1",
            text="Без изменений",
        )
        self.make_chunk(
            version=version_two,
            chunk_index=1,
            heading="Раздел 1",
            section_path="Раздел 1",
            text="Без изменений",
        )

        url = reverse("compare-versions")
        response = self.client.get(
            url,
            {
                "from_version": version_one.id,
                "to_version": version_two.id,
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["identical"])
        self.assertEqual(response.data["summary"]["added"], 0)
        self.assertEqual(response.data["summary"]["removed"], 0)
        self.assertEqual(response.data["summary"]["modified"], 0)
        self.assertEqual(response.data["summary"]["moved"], 0)
        self.assertEqual(response.data["summary"]["unchanged"], 1)
        self.assertIn("by_type", response.data["summary"])
        self.assertEqual(response.data["added"], [])
        self.assertEqual(response.data["removed"], [])
        self.assertEqual(response.data["modified"], [])
        self.assertEqual(response.data["moved"], [])
        self.assertEqual(response.data["text_diff"], "")

    def test_compare_versions_returns_404_for_unknown_version(self):
        document = Document.objects.create(title="Документ", description="")
        version_one = self.make_version(
            document=document,
            version_number=1,
            text="Текст",
            filename="v1.txt",
        )

        url = reverse("compare-versions")
        response = self.client.get(
            url,
            {
                "from_version": version_one.id,
                "to_version": 999999,
            },
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_compare_versions_brief_returns_human_readable_summary(self):
        document = Document.objects.create(
            title="Краткая сводка",
            description="",
        )

        version_one = self.make_version(
            document=document,
            version_number=1,
            text="Старая версия",
            filename="brief1.txt",
        )
        version_two = self.make_version(
            document=document,
            version_number=2,
            text="Новая версия",
            filename="brief2.txt",
        )

        self.make_chunk(
            version=version_one,
            chunk_index=1,
            heading="Раздел 1",
            section_path="Раздел 1",
            text="Старый порядок согласования",
        )
        self.make_chunk(
            version=version_two,
            chunk_index=1,
            heading="Раздел 1",
            section_path="Раздел 1",
            text="Новый порядок согласования",
        )
        self.make_chunk(
            version=version_two,
            chunk_index=2,
            heading="Раздел 2",
            section_path="Раздел 2",
            text="Добавлен новый раздел контроля",
        )

        url = reverse("compare-versions-brief")
        response = self.client.get(
            url,
            {
                "from_version": version_one.id,
                "to_version": version_two.id,
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["identical"])
        self.assertIn("Добавлено фрагментов: 1.", response.data["brief_text"])
        self.assertIn("Изменено фрагментов: 1.", response.data["brief_text"])
        self.assertEqual(response.data["summary"]["added"], 1)
        self.assertEqual(response.data["summary"]["modified"], 1)
        self.assertEqual(len(response.data["highlights"]), 2)
        self.assertEqual(response.data["highlights"][0]["type"], "added")
        self.assertEqual(response.data["highlights"][1]["type"], "modified")

    def test_compare_versions_quiz_returns_questions(self):
        document = Document.objects.create(
            title="Вопросы по изменениям",
            description="",
        )

        version_one = self.make_version(
            document=document,
            version_number=1,
            text="Старая редакция",
            filename="quiz1.txt",
        )
        version_two = self.make_version(
            document=document,
            version_number=2,
            text="Новая редакция",
            filename="quiz2.txt",
        )

        self.make_chunk(
            version=version_one,
            chunk_index=1,
            heading="Раздел 1",
            section_path="Раздел 1",
            text="Старый текст порядка согласования",
        )
        self.make_chunk(
            version=version_two,
            chunk_index=1,
            heading="Раздел 1",
            section_path="Раздел 1",
            text="Новый текст порядка согласования",
        )
        self.make_chunk(
            version=version_two,
            chunk_index=2,
            heading="Раздел 2",
            section_path="Раздел 2",
            text="Добавлены новые правила контроля",
        )

        url = reverse("compare-versions-quiz")
        response = self.client.get(
            url,
            {
                "from_version": version_one.id,
                "to_version": version_two.id,
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["identical"])
        self.assertEqual(response.data["questions_count"], 2)
        self.assertEqual(len(response.data["questions"]), 2)
        self.assertEqual(response.data["questions"][0]["type"], "added")
        self.assertEqual(response.data["questions"][1]["type"], "modified")
        self.assertIn("Что нового добавлено", response.data["questions"][0]["question"])
        self.assertIn("Что изменилось", response.data["questions"][1]["question"])

    def test_save_versions_quiz_and_list_saved_quizzes(self):
        document = Document.objects.create(
            title="Сохранение квиза",
            description="",
        )

        version_one = self.make_version(
            document=document,
            version_number=1,
            text="Старая версия",
            filename="save1.txt",
        )
        version_two = self.make_version(
            document=document,
            version_number=2,
            text="Новая версия",
            filename="save2.txt",
        )

        self.make_chunk(
            version=version_one,
            chunk_index=1,
            heading="Раздел 1",
            section_path="Раздел 1",
            text="Старый текст процедуры",
        )
        self.make_chunk(
            version=version_two,
            chunk_index=1,
            heading="Раздел 1",
            section_path="Раздел 1",
            text="Новый текст процедуры",
        )
        self.make_chunk(
            version=version_two,
            chunk_index=2,
            heading="Раздел 2",
            section_path="Раздел 2",
            text="Добавлен новый контрольный блок",
        )

        save_url = reverse("save-versions-quiz")
        save_response = self.client.post(
            save_url,
            {
                "from_version": version_one.id,
                "to_version": version_two.id,
                "title": "Контроль по изменениям",
                "limit": 5,
            },
            format="json",
        )

        self.assertEqual(save_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(save_response.data["title"], "Контроль по изменениям")
        self.assertEqual(save_response.data["questions_count"], 2)
        self.assertEqual(GeneratedQuiz.objects.count(), 1)

        list_url = reverse("list-saved-quizzes")
        list_response = self.client.get(list_url)

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data), 1)
        self.assertEqual(list_response.data[0]["title"], "Контроль по изменениям")
        self.assertEqual(list_response.data[0]["questions_count"], 2)

    def test_submit_quiz_attempt_and_list_attempts(self):
        document = Document.objects.create(
            title="Прохождение квиза",
            description="",
        )

        version_one = self.make_version(
            document=document,
            version_number=1,
            text="Старая версия",
            filename="attempt1.txt",
        )
        version_two = self.make_version(
            document=document,
            version_number=2,
            text="Новая версия",
            filename="attempt2.txt",
        )

        self.make_chunk(
            version=version_one,
            chunk_index=1,
            heading="Раздел 1",
            section_path="Раздел 1",
            text="Старый текст процедуры",
        )
        self.make_chunk(
            version=version_two,
            chunk_index=1,
            heading="Раздел 1",
            section_path="Раздел 1",
            text="Новый текст процедуры",
        )
        self.make_chunk(
            version=version_two,
            chunk_index=2,
            heading="Раздел 2",
            section_path="Раздел 2",
            text="Добавлен новый контрольный блок",
        )

        save_url = reverse("save-versions-quiz")
        save_response = self.client.post(
            save_url,
            {
                "from_version": version_one.id,
                "to_version": version_two.id,
                "title": "Квиз для прохождения",
                "limit": 5,
            },
            format="json",
        )

        self.assertEqual(save_response.status_code, status.HTTP_201_CREATED)
        quiz_id = save_response.data["id"]

        approve_url = reverse("approve-quiz", kwargs={"quiz_id": quiz_id})
        approve_response = self.client.post(
            approve_url,
            {
                "approved_by_name": "Иванова Е.А.",
                "approval_comment": "Готово к выдаче.",
            },
            format="json",
        )

        self.assertEqual(approve_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            approve_response.data["status"],
            GeneratedQuiz.Status.APPROVED,
        )

        questions = save_response.data["payload"]["questions"]
        self.assertEqual(len(questions), 2)

        submit_url = reverse("submit-quiz-attempt", kwargs={"quiz_id": quiz_id})
        submit_response = self.client.post(
            submit_url,
            {
                "participant_name": "Tester",
                "answers": [
                    {
                        "question_index": 0,
                        "answer": questions[0]["answer"],
                    },
                    {
                        "question_index": 1,
                        "answer": "неверный ответ",
                    },
                ],
            },
            format="json",
        )

        self.assertEqual(submit_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(submit_response.data["participant_name"], "Tester")
        self.assertEqual(submit_response.data["score"], 1)
        self.assertEqual(submit_response.data["total_questions"], 2)
        self.assertEqual(len(submit_response.data["answers"]), 2)

        list_url = reverse("list-quiz-attempts", kwargs={"quiz_id": quiz_id})
        list_response = self.client.get(list_url)

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data), 1)
        self.assertEqual(list_response.data[0]["score"], 1)
        self.assertEqual(list_response.data[0]["total_questions"], 2)

    def test_save_versions_quiz_rejects_identical_versions(self):
        document = Document.objects.create(
            title="Идентичные версии",
            description="",
        )

        version_one = self.make_version(
            document=document,
            version_number=1,
            text="Одинаковый текст",
            filename="same1.txt",
        )
        version_two = self.make_version(
            document=document,
            version_number=2,
            text="Одинаковый текст",
            filename="same2.txt",
        )

        self.make_chunk(
            version=version_one,
            chunk_index=1,
            heading="Раздел 1",
            section_path="Раздел 1",
            text="Без изменений",
        )
        self.make_chunk(
            version=version_two,
            chunk_index=1,
            heading="Раздел 1",
            section_path="Раздел 1",
            text="Без изменений",
        )

        url = reverse("save-versions-quiz")
        response = self.client.post(
            url,
            {
                "from_version": version_one.id,
                "to_version": version_two.id,
                "title": "Пустой квиз",
                "limit": 5,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("there are no changes", response.data["detail"])

    def test_submit_quiz_attempt_rejects_unapproved_quiz(self):
        document = Document.objects.create(
            title="Неутверждённый квиз",
            description="",
        )

        version_one = self.make_version(
            document=document,
            version_number=1,
            text="Старая версия",
            filename="draft1.txt",
        )
        version_two = self.make_version(
            document=document,
            version_number=2,
            text="Новая версия",
            filename="draft2.txt",
        )

        quiz = GeneratedQuiz.objects.create(
            from_version=version_one,
            to_version=version_two,
            title="Черновик квиза",
            payload={
                "from_version": {
                    "id": version_one.id,
                    "document_id": document.id,
                    "version_number": version_one.version_number,
                    "created_at": version_one.created_at.isoformat(),
                },
                "to_version": {
                    "id": version_two.id,
                    "document_id": document.id,
                    "version_number": version_two.version_number,
                    "created_at": version_two.created_at.isoformat(),
                },
                "identical": False,
                "questions_count": 1,
                "questions": [
                    {
                        "question": "Что изменилось?",
                        "answer": "Изменился порядок действий",
                    }
                ],
            },
            questions_count=1,
        )

        url = reverse("submit-quiz-attempt", kwargs={"quiz_id": quiz.id})
        response = self.client.post(
            url,
            {
                "participant_name": "Tester",
                "answers": [
                    {
                        "question_index": 0,
                        "answer": "Изменился порядок действий",
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["detail"],
            "Quiz must be approved before it can be assigned.",
        )

    def test_submit_quiz_attempt_rejects_empty_quiz(self):
        document = Document.objects.create(
            title="Пустой квиз",
            description="",
        )

        version_one = self.make_version(
            document=document,
            version_number=1,
            text="Одинаковый текст",
            filename="empty1.txt",
        )
        version_two = self.make_version(
            document=document,
            version_number=2,
            text="Одинаковый текст",
            filename="empty2.txt",
        )

        quiz = GeneratedQuiz.objects.create(
            from_version=version_one,
            to_version=version_two,
            title="Пустой квиз",
            payload={
                "from_version": {
                    "id": version_one.id,
                    "document_id": document.id,
                    "version_number": version_one.version_number,
                    "created_at": version_one.created_at.isoformat(),
                },
                "to_version": {
                    "id": version_two.id,
                    "document_id": document.id,
                    "version_number": version_two.version_number,
                    "created_at": version_two.created_at.isoformat(),
                },
                "identical": True,
                "questions_count": 0,
                "questions": [],
            },
            questions_count=0,
            status=GeneratedQuiz.Status.APPROVED,
            approved_by_name="Иванова Е.А.",
        )

        url = reverse("submit-quiz-attempt", kwargs={"quiz_id": quiz.id})
        response = self.client.post(
            url,
            {
                "participant_name": "Tester",
                "answers": [],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["detail"],
            "Cannot submit an attempt for an empty quiz.",
        )


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class BaselineEntityExtractionTests(APITestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def make_version(
        self,
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

    def test_extract_entities_from_text_returns_expected_domain_entities(self):
        text = (
            "1. Общий срок предоставления государственной услуги составляет "
            "7 рабочих дней со дня регистрации заявления.\n"
            "2. В случае направления межведомственного запроса срок может быть "
            "продлен, но не более чем на 2 рабочих дня.\n"
            "3. Сотрудник обязан проверить комплектность обязательных документов "
            "до регистрации заявления.\n"
            "4. Для получения услуги заявитель представляет:\n"
            "1) заявление по установленной форме;\n"
            "2) паспорт гражданина Российской Федерации;\n"
            "3) документ, подтверждающий место жительства.\n"
            "5. В предоставлении услуги отказывается в случае:\n"
            "1) представления неполного комплекта документов;\n"
            "2) представления недостоверных сведений.\n"
        )

        entities = extract_entities_from_text(
            text,
            heading="Срок предоставления услуги",
            section_path="Раздел II > Статья 2",
        )

        entity_types = {entity["entity_type"] for entity in entities}

        self.assertIn(EntityType.DEADLINE.value, entity_types)
        self.assertIn(EntityType.CONDITION.value, entity_types)
        self.assertIn(EntityType.OBLIGATION.value, entity_types)
        self.assertIn(EntityType.REQUIRED_DOCUMENT.value, entity_types)
        self.assertIn(EntityType.REFUSAL_REASON.value, entity_types)
        self.assertIn(EntityType.APPLICANT_CATEGORY.value, entity_types)
        self.assertIn(EntityType.SERVICE.value, entity_types)

        deadlines = [
            entity
            for entity in entities
            if entity["entity_type"] == EntityType.DEADLINE.value
        ]
        self.assertTrue(any(item["deadline_value"] == 7 for item in deadlines))
        self.assertTrue(any(item["deadline_value"] == 2 for item in deadlines))

        obligations = [
            entity
            for entity in entities
            if entity["entity_type"] == EntityType.OBLIGATION.value
        ]
        self.assertTrue(
            any(
                item["obligation_phase"] == "before_registration"
                for item in obligations
            )
        )

        documents = [
            entity
            for entity in entities
            if entity["entity_type"] == EntityType.REQUIRED_DOCUMENT.value
        ]
        self.assertTrue(
            any(
                item["document_name"] == "заявление по установленной форме"
                for item in documents
            )
        )
        self.assertTrue(
            any(
                item["document_name"] == "паспорт гражданина Российской Федерации"
                for item in documents
            )
        )

        refusal_reasons = [
            entity
            for entity in entities
            if entity["entity_type"] == EntityType.REFUSAL_REASON.value
        ]
        self.assertTrue(
            any(
                item["refusal_category"] == "incomplete_documents"
                for item in refusal_reasons
            )
        )
        self.assertTrue(
            any(
                item["refusal_category"] == "false_information"
                for item in refusal_reasons
            )
        )

    def test_analyze_version_entities_saves_result_in_database(self):
        document = Document.objects.create(
            title="Анализ сущностей",
            description="Тест baseline extraction",
        )

        version = self.make_version(
            document=document,
            version_number=1,
            text="Тестовая версия",
            filename="analysis_v1.txt",
        )

        chunk_one = self.make_chunk(
            version=version,
            chunk_index=1,
            heading="Срок предоставления услуги",
            section_path="Раздел II > Статья 2",
            text=(
                "Общий срок предоставления государственной услуги составляет "
                "7 рабочих дней со дня регистрации заявления."
            ),
        )
        chunk_two = self.make_chunk(
            version=version,
            chunk_index=2,
            heading="Документы, представляемые заявителем",
            section_path="Раздел II > Статья 3",
            text=(
                "Для получения услуги заявитель представляет:\n"
                "1) заявление по установленной форме;\n"
                "2) паспорт гражданина Российской Федерации."
            ),
        )

        result = analyze_version_entities(version)

        self.assertEqual(result["version_id"], version.id)
        self.assertEqual(result["chunks_count"], 2)
        self.assertGreaterEqual(result["entities_count"], 3)

        analyses = ChunkAnalysis.objects.filter(
            chunk__version=version,
            extraction_method="rule_based",
        ).order_by("chunk__chunk_index")

        self.assertEqual(analyses.count(), 2)

        first_analysis = analyses[0]
        second_analysis = analyses[1]

        self.assertEqual(first_analysis.chunk_id, chunk_one.id)
        self.assertGreaterEqual(first_analysis.entities_count, 1)
        self.assertTrue(
            any(
                entity["entity_type"] == EntityType.DEADLINE.value
                for entity in first_analysis.entities
            )
        )

        self.assertEqual(second_analysis.chunk_id, chunk_two.id)
        self.assertGreaterEqual(second_analysis.entities_count, 2)
        self.assertTrue(
            any(
                entity["entity_type"] == EntityType.REQUIRED_DOCUMENT.value
                for entity in second_analysis.entities
            )
        )

    def test_analyze_version_entities_updates_existing_analysis(self):
        document = Document.objects.create(
            title="Повторный анализ",
            description="",
        )

        version = self.make_version(
            document=document,
            version_number=1,
            text="Версия",
            filename="repeat.txt",
        )

        chunk = self.make_chunk(
            version=version,
            chunk_index=1,
            heading="Основания отказа",
            section_path="Раздел II > Статья 4",
            text=(
                "В предоставлении услуги отказывается в случае:\n"
                "1) представления неполного комплекта документов;\n"
                "2) представления недостоверных сведений."
            ),
        )

        first_result = analyze_version_entities(version)
        second_result = analyze_version_entities(version)

        self.assertEqual(first_result["chunks_count"], 1)
        self.assertEqual(second_result["chunks_count"], 1)

        analyses = ChunkAnalysis.objects.filter(
            chunk=chunk,
            extraction_method="rule_based",
        )
        self.assertEqual(analyses.count(), 1)
        self.assertGreaterEqual(analyses.first().entities_count, 2)


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class LLMEntityExtractionModeTests(APITestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def make_version(
        self,
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

    def test_extract_entities_by_mode_llm_uses_llm_extractor(self):
        fake_llm_extractor = Mock()
        fake_llm_extractor.extract.return_value = [
            {
                "entity_type": EntityType.DEADLINE.value,
                "value": "7 рабочих дней",
                "normalized_value": "P7_WORKING_DAYS",
                "confidence": 0.98,
                "source_text": "Срок составляет 7 рабочих дней.",
                "start_char": 16,
                "end_char": 30,
                "heading": "Срок предоставления услуги",
                "section_path": "Раздел II > Статья 2",
                "extraction_method": ExtractionMethod.LLM.value,
                "deadline_value": 7,
                "deadline_unit": "working_days",
                "deadline_modifier": "exact",
                "deadline_scope": "service_provision",
            }
        ]

        entities = extract_entities_by_mode(
            "Срок составляет 7 рабочих дней.",
            heading="Срок предоставления услуги",
            section_path="Раздел II > Статья 2",
            mode="llm",
            llm_extractor=fake_llm_extractor,
        )

        self.assertEqual(len(entities), 1)
        self.assertEqual(entities[0]["entity_type"], EntityType.DEADLINE.value)
        self.assertEqual(
            entities[0]["extraction_method"],
            ExtractionMethod.LLM.value,
        )
        fake_llm_extractor.extract.assert_called_once()

    def test_analyze_chunk_entities_hybrid_merges_rule_and_llm_entities(self):
        document = Document.objects.create(
            title="Hybrid extraction",
            description="",
        )
        version = self.make_version(
            document=document,
            version_number=1,
            text="Текст",
            filename="hybrid.txt",
        )
        chunk = self.make_chunk(
            version=version,
            chunk_index=1,
            heading="Срок предоставления услуги",
            section_path="Раздел II > Статья 2",
            text=(
                "Общий срок предоставления государственной услуги составляет "
                "7 рабочих дней."
            ),
        )

        fake_llm_extractor = Mock()
        fake_llm_extractor.extract.return_value = [
            {
                "entity_type": EntityType.SERVICE.value,
                "value": "государственной услуги",
                "normalized_value": "государственная услуга",
                "confidence": 0.93,
                "source_text": chunk.text,
                "start_char": 29,
                "end_char": 51,
                "heading": chunk.heading,
                "section_path": chunk.section_path,
                "extraction_method": ExtractionMethod.LLM.value,
                "service_name": "государственная услуга",
                "service_action": "предоставление",
            }
        ]

        analysis = analyze_chunk_entities(
            chunk,
            mode="hybrid",
            llm_extractor=fake_llm_extractor,
        )

        self.assertEqual(
            analysis.extraction_method,
            ExtractionMethod.HYBRID.value,
        )
        self.assertGreaterEqual(analysis.entities_count, 2)
        self.assertTrue(
            any(
                entity["entity_type"] == EntityType.DEADLINE.value
                for entity in analysis.entities
            )
        )
        self.assertTrue(
            any(
                entity["entity_type"] == EntityType.SERVICE.value
                for entity in analysis.entities
            )
        )
        self.assertTrue(
            all(
                entity["extraction_method"] == ExtractionMethod.HYBRID.value
                for entity in analysis.entities
            )
        )

    def test_analyze_version_entities_llm_saves_database_result(self):
        document = Document.objects.create(
            title="LLM extraction DB",
            description="",
        )
        version = self.make_version(
            document=document,
            version_number=1,
            text="Текст",
            filename="llm_db.txt",
        )
        chunk = self.make_chunk(
            version=version,
            chunk_index=1,
            heading="Основания отказа",
            section_path="Раздел II > Статья 4",
            text=(
                "В предоставлении услуги отказывается в случае "
                "представления неполного комплекта документов."
            ),
        )

        fake_llm_extractor = Mock()
        fake_llm_extractor.extract.return_value = [
            {
                "entity_type": EntityType.REFUSAL_REASON.value,
                "value": "представления неполного комплекта документов",
                "normalized_value": "неполный комплект документов",
                "confidence": 0.96,
                "source_text": chunk.text,
                "start_char": 49,
                "end_char": 92,
                "heading": chunk.heading,
                "section_path": chunk.section_path,
                "extraction_method": ExtractionMethod.LLM.value,
                "refusal_reason_text": "представления неполного комплекта документов",
                "refusal_category": "incomplete_documents",
            }
        ]

        result = analyze_version_entities(
            version,
            mode="llm",
            llm_extractor=fake_llm_extractor,
        )

        self.assertEqual(result["version_id"], version.id)
        self.assertEqual(
            result["extraction_method"],
            ExtractionMethod.LLM.value,
        )

        analysis = ChunkAnalysis.objects.get(
            chunk=chunk,
            extraction_method=ExtractionMethod.LLM.value,
        )
        self.assertEqual(analysis.entities_count, 1)
        self.assertEqual(
            analysis.entities[0]["entity_type"],
            EntityType.REFUSAL_REASON.value,
        )


class LLMEntityPostprocessingTests(SimpleTestCase):
    def test_llm_sanitize_deadline_entity_adds_structured_fields(self):
        from documents.llm_entity_extraction import _sanitize_entity

        entity = _sanitize_entity(
            {
                "entity_type": "deadline",
                "value": "7 рабочих дней",
                "normalized_value": "7 рабочих дней",
                "confidence": 0.95,
            },
            source_text="Общий срок составляет 7 рабочих дней.",
            heading="Срок предоставления услуги",
            section_path="Раздел II > Статья 2",
            extraction_method="llm",
        )

        self.assertIsNotNone(entity)
        self.assertEqual(entity["deadline_value"], 7)
        self.assertEqual(entity["deadline_unit"], "working_days")
        self.assertEqual(entity["deadline_modifier"], "exact")
        self.assertEqual(entity["deadline_scope"], "service_provision")
        self.assertEqual(entity["normalized_value"], "P7_WORKING_DAYS")

    def test_llm_sanitize_required_document_entity_adds_actor_and_role(self):
        from documents.llm_entity_extraction import _sanitize_entity

        entity = _sanitize_entity(
            {
                "entity_type": "required_document",
                "value": "документ, подтверждающий полномочия представителя",
                "normalized_value": "",
                "confidence": 0.9,
            },
            source_text="Дополнительно представляется документ, подтверждающий полномочия представителя.",
            heading="Документы",
            section_path="Раздел II > Статья 2",
            extraction_method="llm",
        )

        self.assertIsNotNone(entity)
        self.assertEqual(entity["for_actor"], "representative")
        self.assertEqual(entity["document_role"], "additional")
        self.assertEqual(
            entity["document_name"],
            "документ, подтверждающий полномочия представителя",
        )

    def test_llm_sanitize_refusal_reason_entity_adds_category(self):
        from documents.llm_entity_extraction import _sanitize_entity

        entity = _sanitize_entity(
            {
                "entity_type": "refusal_reason",
                "value": "представления недостоверных сведений",
                "normalized_value": "",
                "confidence": 0.92,
            },
            source_text="1) представления недостоверных сведений;",
            heading="Основания отказа",
            section_path="Раздел II > Статья 2",
            extraction_method="llm",
        )

        self.assertIsNotNone(entity)
        self.assertEqual(entity["refusal_category"], "false_information")
        self.assertEqual(
            entity["refusal_reason_text"],
            "представления недостоверных сведений",
        )


class ChangeClassificationUnitTests(SimpleTestCase):
    def test_classify_deadline_modified_chunk_pair(self):
        from documents.change_classification import classify_modified_chunk_pair

        classification = classify_modified_chunk_pair(
            from_chunk={
                "id": 1,
                "chunk_index": 1,
                "heading": "Срок предоставления услуги",
                "section_path": "Раздел II > Статья 2",
                "text": (
                    "Общий срок предоставления государственной услуги "
                    "составляет 10 рабочих дней."
                ),
                "text_hash": "a",
            },
            to_chunk={
                "id": 2,
                "chunk_index": 1,
                "heading": "Срок предоставления услуги",
                "section_path": "Раздел II > Статья 2",
                "text": (
                    "Общий срок предоставления государственной услуги "
                    "составляет 7 рабочих дней."
                ),
                "text_hash": "b",
            },
            similarity=0.95,
            match_reason="section_path",
        )

        self.assertEqual(
            classification["primary_type"],
            ChangeType.DEADLINE.value,
        )
        self.assertIn(
            ChangeType.DEADLINE.value,
            classification["matched_types"],
        )

    def test_classify_document_added_chunk(self):
        from documents.change_classification import classify_added_or_removed_chunk

        classification = classify_added_or_removed_chunk(
            {
                "id": 1,
                "chunk_index": 2,
                "heading": "Документы, представляемые заявителем",
                "section_path": "Раздел II > Статья 2",
                "text": (
                    "Для получения услуги заявитель представляет:\n"
                    "1) заявление по установленной форме;\n"
                    "2) паспорт гражданина Российской Федерации;\n"
                    "3) согласие на обработку персональных данных."
                ),
                "text_hash": "x",
            },
            operation="added",
        )

        self.assertEqual(
            classification["primary_type"],
            ChangeType.DOCUMENT.value,
        )

    def test_classify_moved_chunk_pair_as_structural(self):
        from documents.change_classification import classify_moved_chunk_pair

        classification = classify_moved_chunk_pair(
            from_chunk={
                "id": 1,
                "chunk_index": 1,
                "heading": "Статья 2",
                "section_path": "Раздел I > Статья 2",
                "text": "Одинаковый текст фрагмента.",
                "text_hash": "same",
            },
            to_chunk={
                "id": 2,
                "chunk_index": 3,
                "heading": "Статья 4",
                "section_path": "Раздел II > Статья 4",
                "text": "Одинаковый текст фрагмента.",
                "text_hash": "same",
            },
        )

        self.assertEqual(
            classification["primary_type"],
            ChangeType.STRUCTURAL.value,
        )

    def test_classify_editorial_modified_chunk_pair(self):
        from documents.change_classification import classify_modified_chunk_pair

        classification = classify_modified_chunk_pair(
            from_chunk={
                "id": 1,
                "chunk_index": 1,
                "heading": "Общие положения",
                "section_path": "Раздел I > Статья 1",
                "text": (
                    "Текст материалов должен быть изложен ясно и последовательно."
                ),
                "text_hash": "left",
            },
            to_chunk={
                "id": 2,
                "chunk_index": 1,
                "heading": "Общие положения",
                "section_path": "Раздел I > Статья 1",
                "text": (
                    "Текст информационных материалов должен быть изложен ясно "
                    "и последовательно."
                ),
                "text_hash": "right",
            },
            similarity=0.97,
            match_reason="section_path",
        )

        self.assertEqual(
            classification["primary_type"],
            ChangeType.EDITORIAL.value,
        )


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class ChangeClassificationIntegrationTests(APITestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def make_version(
        self,
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

    def test_build_version_diff_contains_change_types_summary(self):
        document = Document.objects.create(
            title="Классификация изменений",
            description="",
        )

        version_one = self.make_version(
            document=document,
            version_number=1,
            text="v1",
            filename="v1.txt",
        )
        version_two = self.make_version(
            document=document,
            version_number=2,
            text="v2",
            filename="v2.txt",
        )

        self.make_chunk(
            version=version_one,
            chunk_index=1,
            heading="Срок предоставления услуги",
            section_path="Раздел II > Статья 2",
            text=(
                "Общий срок предоставления государственной услуги составляет "
                "10 рабочих дней."
            ),
        )
        self.make_chunk(
            version=version_two,
            chunk_index=1,
            heading="Срок предоставления услуги",
            section_path="Раздел II > Статья 2",
            text=(
                "Общий срок предоставления государственной услуги составляет "
                "7 рабочих дней."
            ),
        )

        diff_payload = build_version_diff(
            from_version=version_one,
            to_version=version_two,
        )

        self.assertIn("by_type", diff_payload["summary"])
        self.assertEqual(
            diff_payload["summary"]["by_type"][ChangeType.DEADLINE.value],
            1,
        )
        self.assertEqual(len(diff_payload["modified"]), 1)
        self.assertEqual(
            diff_payload["modified"][0]["change_classification"]["primary_type"],
            ChangeType.DEADLINE.value,
        )

    def test_compare_endpoint_returns_change_classification(self):
        document = Document.objects.create(
            title="API классификация",
            description="",
        )

        version_one = self.make_version(
            document=document,
            version_number=1,
            text="v1",
            filename="api_v1.txt",
        )
        version_two = self.make_version(
            document=document,
            version_number=2,
            text="v2",
            filename="api_v2.txt",
        )

        self.make_chunk(
            version=version_one,
            chunk_index=1,
            heading="Основания отказа",
            section_path="Раздел II > Статья 2",
            text=(
                "В предоставлении услуги отказывается в случае:\n"
                "1) представления неполного комплекта документов."
            ),
        )
        self.make_chunk(
            version=version_two,
            chunk_index=1,
            heading="Основания отказа",
            section_path="Раздел II > Статья 2",
            text=(
                "В предоставлении услуги отказывается в случае:\n"
                "1) представления неполного комплекта документов;\n"
                "2) представления недостоверных сведений."
            ),
        )

        response = self.client.get(
            "/api/compare/",
            {
                "from_version": version_one.id,
                "to_version": version_two.id,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertIn("by_type", payload["summary"])
        self.assertGreaterEqual(
            payload["summary"]["by_type"][ChangeType.REFUSAL.value],
            1,
        )
        self.assertEqual(len(payload["modified"]), 1)
        self.assertEqual(
            payload["modified"][0]["change_classification"]["primary_type"],
            ChangeType.REFUSAL.value,
        )
