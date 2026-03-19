from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import TestCase

from ..models import (
    Answer,
    Choice,
    Chunk,
    Document,
    DocumentVersion,
    Employee,
    GeneratedQuiz,
    Question,
    QuizAttempt,
    Summary,
    VersionChangeItem,
    VersionComparison,
)


class Phase3DomainModelTests(TestCase):
    def make_version(self, document: Document, version_number: int) -> DocumentVersion:
        return DocumentVersion.objects.create(
            document=document,
            version_number=version_number,
            source_filename=f"v{version_number}.txt",
            file=SimpleUploadedFile(
                name=f"v{version_number}.txt",
                content=f"version-{version_number}".encode("utf-8"),
                content_type="text/plain",
            ),
            extracted_text=f"Version {version_number}",
            normalized_text=f"version {version_number}",
            content_hash=f"hash-{version_number}",
        )

    def test_comparison_summary_quiz_attempt_route_is_represented(self):
        document = Document.objects.create(title="Регламент")
        version_one = self.make_version(document=document, version_number=1)
        version_two = self.make_version(document=document, version_number=2)

        old_chunk = Chunk.objects.create(
            version=version_one,
            chunk_index=1,
            heading="Пункт 1",
            section_path="1",
            text="Старый текст",
            text_hash="old-1",
        )
        new_chunk = Chunk.objects.create(
            version=version_two,
            chunk_index=1,
            heading="Пункт 1",
            section_path="1",
            text="Новый текст",
            text_hash="new-1",
        )

        comparison = VersionComparison.objects.create(
            document=document,
            from_version=version_one,
            to_version=version_two,
            status=VersionComparison.Status.COMPLETED,
        )
        change_item = VersionChangeItem.objects.create(
            comparison=comparison,
            change_type=VersionChangeItem.ChangeType.MODIFIED,
            old_chunk=old_chunk,
            new_chunk=new_chunk,
            similarity=0.8,
            match_reason="section_path",
            sort_order=1,
        )
        summary = Summary.objects.create(
            comparison=comparison,
            text="Изменён порядок выполнения процедуры.",
            highlights=["Срок стал короче"],
        )
        quiz = GeneratedQuiz.objects.create(
            comparison=comparison,
            summary=summary,
            from_version=version_one,
            to_version=version_two,
            title="Проверка по изменениям",
            questions_count=1,
        )
        question = Question.objects.create(
            quiz=quiz,
            source_change_item=change_item,
            order=1,
            question_type=Question.QuestionType.SINGLE_CHOICE,
            prompt="Что изменилось в пункте 1?",
            explanation="Вопрос привязан к конкретному изменению.",
        )
        correct_choice = Choice.objects.create(
            question=question,
            order=1,
            text="Срок сократили",
            is_correct=True,
        )
        Choice.objects.create(
            question=question,
            order=2,
            text="Срок увеличили",
            is_correct=False,
        )
        employee = Employee.objects.create(
            full_name="Иванов Иван Иванович",
            department="МФЦ",
        )
        attempt = QuizAttempt.objects.create(
            quiz=quiz,
            employee=employee,
            participant_name=employee.full_name,
            score=1,
            total_questions=1,
            status=QuizAttempt.Status.COMPLETED,
        )
        answer = Answer.objects.create(
            attempt=attempt,
            question=question,
            selected_choice=correct_choice,
            is_correct=True,
        )

        self.assertEqual(document.versions.count(), 2)
        self.assertEqual(comparison.change_items.count(), 1)
        self.assertEqual(comparison.summary, summary)
        self.assertEqual(quiz.questions.count(), 1)
        self.assertEqual(question.choices.count(), 2)
        self.assertEqual(attempt.answer_items.count(), 1)
        self.assertTrue(answer.is_correct)

    def test_chunk_index_is_unique_inside_version(self):
        document = Document.objects.create(title="Положение")
        version = self.make_version(document=document, version_number=1)

        Chunk.objects.create(
            version=version,
            chunk_index=1,
            heading="Пункт 1",
            section_path="1",
            text="Текст 1",
            text_hash="h1",
        )

        with self.assertRaises(IntegrityError):
            Chunk.objects.create(
                version=version,
                chunk_index=1,
                heading="Пункт 1.1",
                section_path="1.1",
                text="Текст 2",
                text_hash="h2",
            )

    def test_answer_is_unique_per_attempt_and_question(self):
        document = Document.objects.create(title="Инструкция")
        version_one = self.make_version(document=document, version_number=1)
        version_two = self.make_version(document=document, version_number=2)
        comparison = VersionComparison.objects.create(
            document=document,
            from_version=version_one,
            to_version=version_two,
        )
        summary = Summary.objects.create(
            comparison=comparison,
            text="Краткая выжимка",
        )
        quiz = GeneratedQuiz.objects.create(
            comparison=comparison,
            summary=summary,
            from_version=version_one,
            to_version=version_two,
            title="Тест",
            questions_count=1,
        )
        question = Question.objects.create(
            quiz=quiz,
            order=1,
            prompt="Что изменилось?",
        )
        attempt = QuizAttempt.objects.create(
            quiz=quiz,
            participant_name="Петров Петр Петрович",
            total_questions=1,
        )

        Answer.objects.create(
            attempt=attempt,
            question=question,
            text_answer="Ответ 1",
            is_correct=False,
        )

        with self.assertRaises(IntegrityError):
            Answer.objects.create(
                attempt=attempt,
                question=question,
                text_answer="Ответ 2",
                is_correct=False,
            )
