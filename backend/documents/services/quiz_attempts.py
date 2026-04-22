from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils import timezone

from ..models import Answer, GeneratedQuiz, Question, QuizAttempt
from .exceptions import DomainWorkflowError


QUIZ_ATTEMPT_BLOCKED_STATUS_MESSAGES = {
    GeneratedQuiz.Status.DRAFT: "Quiz is still a draft and must be submitted for review first.",
    GeneratedQuiz.Status.PENDING_REVIEW: "Quiz is pending review and cannot be assigned yet.",
    GeneratedQuiz.Status.REJECTED: "Rejected quiz cannot be assigned until it is resubmitted and approved.",
    GeneratedQuiz.Status.SUPERSEDED: "Superseded quiz cannot be assigned because a newer quiz replaced it.",
    GeneratedQuiz.Status.ARCHIVED: "Archived quiz cannot be assigned.",
}


def normalize_text(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def normalize_participant_name(value: str) -> str:
    return " ".join((value or "").strip().split())


def quiz_has_materialized_questions(quiz: GeneratedQuiz) -> bool:
    payload_questions = quiz.payload.get("questions", [])
    if not isinstance(payload_questions, list) or not payload_questions:
        return False
    return quiz.questions.exists()


def _build_submitted_answers_maps(
    submitted_answers: list[dict[str, Any]],
) -> tuple[dict[int, dict[str, Any]], dict[int, dict[str, Any]]]:
    submitted_by_question_id: dict[int, dict[str, Any]] = {}
    submitted_by_index: dict[int, dict[str, Any]] = {}

    for item in submitted_answers:
        try:
            question_id = int(item.get("question_id"))
        except (TypeError, ValueError):
            question_id = None
        if question_id is not None:
            submitted_by_question_id[question_id] = item

        try:
            question_index = int(item.get("question_index"))
        except (TypeError, ValueError):
            question_index = None
        if question_index is not None:
            submitted_by_index[question_index] = item

    return submitted_by_question_id, submitted_by_index


def _resolve_choice_from_payload(
    question: dict[str, Any],
    submitted_item: dict[str, Any],
) -> tuple[dict[str, Any] | None, str]:
    choice_index = submitted_item.get("selected_choice_index")
    if choice_index is not None:
        try:
            expected_index = int(choice_index)
        except (TypeError, ValueError):
            expected_index = None
        if expected_index is not None:
            for choice in question.get("choices", []):
                if choice.get("choice_index") == expected_index:
                    return choice, str(choice.get("text", ""))

    selected_choice_text = str(submitted_item.get("selected_choice_text") or "")
    if selected_choice_text:
        normalized_choice_text = normalize_text(selected_choice_text)
        for choice in question.get("choices", []):
            if normalize_text(str(choice.get("text", ""))) == normalized_choice_text:
                return choice, str(choice.get("text", ""))
        return None, selected_choice_text

    answer_text = str(submitted_item.get("answer") or "")
    if answer_text:
        normalized_answer = normalize_text(answer_text)
        for choice in question.get("choices", []):
            if normalize_text(str(choice.get("text", ""))) == normalized_answer:
                return choice, str(choice.get("text", ""))
        return None, answer_text

    return None, ""


def _resolve_choice_from_question(
    question: Question,
    submitted_item: dict[str, Any],
):
    choices = sorted(question.choices.all(), key=lambda item: (item.order, item.id))

    choice_id = submitted_item.get("selected_choice_id")
    if choice_id is not None:
        try:
            expected_choice_id = int(choice_id)
        except (TypeError, ValueError):
            expected_choice_id = None
        if expected_choice_id is not None:
            for choice in choices:
                if choice.id == expected_choice_id:
                    return choice, choice.text

    choice_index = submitted_item.get("selected_choice_index")
    if choice_index is not None:
        try:
            expected_index = int(choice_index)
        except (TypeError, ValueError):
            expected_index = None
        if expected_index is not None:
            for choice in choices:
                if choice.order == expected_index:
                    return choice, choice.text

    selected_choice_text = str(submitted_item.get("selected_choice_text") or "")
    if selected_choice_text:
        normalized_choice_text = normalize_text(selected_choice_text)
        for choice in choices:
            if normalize_text(choice.text) == normalized_choice_text:
                return choice, choice.text
        return None, selected_choice_text

    answer_text = str(submitted_item.get("answer") or "")
    if answer_text:
        normalized_answer = normalize_text(answer_text)
        for choice in choices:
            if normalize_text(choice.text) == normalized_answer:
                return choice, choice.text
        return None, answer_text

    return None, ""


def resolve_submitted_answer(
    question: dict[str, Any],
    submitted_item: dict[str, Any],
) -> str:
    question_type = question.get("question_type") or question.get("type")

    if question_type == "single_choice":
        _, resolved_text = _resolve_choice_from_payload(question, submitted_item)
        return resolved_text

    return str(submitted_item.get("answer", ""))


def _evaluate_payload_question(
    question_index: int,
    question: dict[str, Any],
    submitted_item: dict[str, Any],
) -> dict[str, Any]:
    question_type = question.get("question_type") or question.get("type")
    selected_choice, resolved_answer = _resolve_choice_from_payload(question, submitted_item)
    if question_type != "single_choice":
        resolved_answer = str(submitted_item.get("answer", ""))

    expected_answer = str(question.get("answer") or "")
    submitted_answer = normalize_text(resolved_answer)
    is_answered = bool(submitted_answer)
    is_correct = is_answered and submitted_answer == normalize_text(expected_answer)

    return {
        "question_id": None,
        "question_index": question_index,
        "question": question.get("question"),
        "expected_answer": expected_answer,
        "submitted_answer": resolved_answer,
        "is_correct": is_correct,
        "type": question.get("type"),
        "question_type": question_type,
        "selected_choice_id": None,
        "text_answer": resolved_answer if selected_choice is None else "",
        "answered": is_answered,
    }


def _evaluate_materialized_question(
    question_index: int,
    question: Question,
    submitted_item: dict[str, Any],
) -> dict[str, Any]:
    question_type = question.question_type
    choices = sorted(question.choices.all(), key=lambda item: (item.order, item.id))
    selected_choice, resolved_answer = _resolve_choice_from_question(question, submitted_item)

    if question_type == Question.QuestionType.SINGLE_CHOICE:
        correct_choice = next((choice for choice in choices if choice.is_correct), None)
        expected_answer = correct_choice.text if correct_choice is not None else ""
        is_answered = selected_choice is not None or bool(normalize_text(resolved_answer))
        is_correct = selected_choice is not None and bool(selected_choice.is_correct)
        text_answer = "" if selected_choice is not None else resolved_answer
    else:
        expected_answer = question.correct_text_answer
        normalized_submitted = normalize_text(str(submitted_item.get("answer") or ""))
        resolved_answer = str(submitted_item.get("answer") or "")
        is_answered = bool(normalized_submitted)
        is_correct = bool(normalized_submitted) and normalized_submitted == normalize_text(expected_answer)
        text_answer = resolved_answer

    return {
        "question_id": question.id,
        "question_index": question_index,
        "question": question.prompt,
        "expected_answer": expected_answer,
        "submitted_answer": resolved_answer,
        "is_correct": is_correct,
        "type": question.question_type,
        "question_type": question.question_type,
        "selected_choice_id": selected_choice.id if selected_choice is not None else None,
        "text_answer": text_answer,
        "answered": is_answered,
    }


def evaluate_quiz_answers(
    quiz_or_payload: GeneratedQuiz | dict[str, Any],
    submitted_answers: list[dict[str, Any]],
) -> dict[str, Any]:
    submitted_by_question_id, submitted_by_index = _build_submitted_answers_maps(submitted_answers)
    results: list[dict[str, Any]] = []

    if isinstance(quiz_or_payload, GeneratedQuiz):
        questions = list(
            quiz_or_payload.questions.prefetch_related("choices").all().order_by("order", "id")
        )
        for index, question in enumerate(questions):
            submitted_item = (
                submitted_by_question_id.get(question.id)
                or submitted_by_index.get(index, {})
            )
            results.append(_evaluate_materialized_question(index, question, submitted_item))
    else:
        questions = quiz_or_payload.get("questions", [])
        for index, question in enumerate(questions):
            results.append(_evaluate_payload_question(index, question, submitted_by_index.get(index, {})))

    total_questions = len(results)
    answered_questions = sum(1 for item in results if item["answered"])
    correct_answers = sum(1 for item in results if item["is_correct"])
    score_percent = round((correct_answers / total_questions) * 100, 2) if total_questions else 0.0

    return {
        "score": correct_answers,
        "total_questions": total_questions,
        "answered_questions": answered_questions,
        "correct_answers": correct_answers,
        "score_percent": score_percent,
        "results": results,
    }


def get_quiz_attempt_block_reason(quiz: GeneratedQuiz) -> str | None:
    if quiz.questions_count <= 0:
        return "Cannot submit an attempt for an empty quiz."

    if quiz.status != GeneratedQuiz.Status.APPROVED:
        return QUIZ_ATTEMPT_BLOCKED_STATUS_MESSAGES.get(
            quiz.status,
            "Quiz must be approved before it can be assigned.",
        )

    if not quiz_has_materialized_questions(quiz):
        return "Cannot submit an attempt for a quiz without materialized questions."

    return None


def ensure_quiz_attempt_allowed(quiz: GeneratedQuiz) -> None:
    reason = get_quiz_attempt_block_reason(quiz)
    if reason is not None:
        raise DomainWorkflowError(reason)


def build_attempt_form_questions(quiz: GeneratedQuiz) -> list[dict[str, Any]]:
    questions = list(quiz.questions.prefetch_related("choices").order_by("order", "id"))
    return [
        {
            "question_id": question.id,
            "question_index": index,
            "question": question.prompt,
            "question_type": question.question_type,
            "choices": [
                {
                    "choice_id": choice.id,
                    "choice_index": choice.order,
                    "text": choice.text,
                    "is_correct": choice.is_correct,
                }
                for choice in sorted(question.choices.all(), key=lambda item: (item.order, item.id))
            ],
        }
        for index, question in enumerate(questions)
    ]


def start_quiz_attempt(
    *,
    quiz: GeneratedQuiz,
    participant_name: str,
    employee=None,
) -> tuple[QuizAttempt, bool]:
    ensure_quiz_attempt_allowed(quiz)

    participant_name = normalize_participant_name(participant_name)
    if not participant_name:
        raise DomainWorkflowError("Field 'participant_name' is required.")

    with transaction.atomic():
        existing_attempt = (
            QuizAttempt.objects.select_for_update()
            .filter(
                quiz=quiz,
                participant_name=participant_name,
                status=QuizAttempt.Status.IN_PROGRESS,
            )
            .order_by("-created_at")
            .first()
        )
        if existing_attempt is not None:
            return existing_attempt, False

        attempt = QuizAttempt.objects.create(
            quiz=quiz,
            employee=employee,
            participant_name=participant_name,
            total_questions=quiz.questions.count(),
            status=QuizAttempt.Status.IN_PROGRESS,
        )

    return attempt, True


@transaction.atomic
def submit_started_quiz_attempt(
    *,
    attempt: QuizAttempt,
    submitted_answers: list[dict[str, Any]],
) -> tuple[QuizAttempt, dict[str, Any]]:
    locked_attempt = (
        QuizAttempt.objects.select_for_update()
        .select_related("quiz")
        .get(pk=attempt.pk)
    )
    if locked_attempt.status != QuizAttempt.Status.IN_PROGRESS:
        raise DomainWorkflowError("Only in-progress attempt can be submitted.")

    questions = list(
        locked_attempt.quiz.questions.prefetch_related("choices").order_by("order", "id")
    )
    if not questions:
        raise DomainWorkflowError("Cannot submit an attempt for a quiz without materialized questions.")

    evaluation = evaluate_quiz_answers(locked_attempt.quiz, submitted_answers)

    Answer.objects.filter(attempt=locked_attempt).delete()
    answer_rows = []
    questions_by_id = {question.id: question for question in questions}

    for result in evaluation["results"]:
        if not result["answered"]:
            continue
        question = questions_by_id.get(result["question_id"])
        if question is None:
            continue
        answer_rows.append(
            Answer(
                attempt=locked_attempt,
                question=question,
                selected_choice_id=result["selected_choice_id"],
                text_answer=result["text_answer"],
                is_correct=bool(result["is_correct"]),
            )
        )

    if answer_rows:
        Answer.objects.bulk_create(answer_rows)

    locked_attempt.answers = evaluation["results"]
    locked_attempt.score = evaluation["score"]
    locked_attempt.total_questions = evaluation["total_questions"]
    locked_attempt.answered_questions = evaluation["answered_questions"]
    locked_attempt.correct_answers = evaluation["correct_answers"]
    locked_attempt.score_percent = evaluation["score_percent"]
    locked_attempt.status = QuizAttempt.Status.COMPLETED
    locked_attempt.submitted_at = timezone.now()
    locked_attempt.completed_at = locked_attempt.submitted_at
    locked_attempt.save(
        update_fields=[
            "answers",
            "score",
            "total_questions",
            "answered_questions",
            "correct_answers",
            "score_percent",
            "status",
            "submitted_at",
            "completed_at",
        ]
    )

    return locked_attempt, evaluation


def record_quiz_attempt(
    *,
    quiz: GeneratedQuiz,
    participant_name: str,
    submitted_answers: list[dict[str, Any]],
) -> tuple[QuizAttempt, dict[str, Any]]:
    attempt, _ = start_quiz_attempt(
        quiz=quiz,
        participant_name=participant_name,
    )
    return submit_started_quiz_attempt(
        attempt=attempt,
        submitted_answers=submitted_answers,
    )
