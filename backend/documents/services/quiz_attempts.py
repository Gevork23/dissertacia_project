from __future__ import annotations

import logging
from typing import Any

from django.db import transaction
from django.utils import timezone

from ..models import Answer, GeneratedQuiz, Question, QuizAttempt
from .exceptions import DomainWorkflowError

logger = logging.getLogger("documents.quiz_attempts")

QUIZ_ATTEMPT_BLOCKED_STATUS_MESSAGES = {
    GeneratedQuiz.Status.DRAFT: "Quiz is still a draft and must be submitted for review first.",
    GeneratedQuiz.Status.PENDING_REVIEW: "Quiz is pending review and cannot be assigned yet.",
    GeneratedQuiz.Status.REJECTED: "Rejected quiz cannot be assigned until it is resubmitted and approved.",
    GeneratedQuiz.Status.SUPERSEDED: "Superseded quiz cannot be assigned because a newer quiz replaced it.",
    GeneratedQuiz.Status.ARCHIVED: "Archived quiz cannot be assigned anymore.",
}


def normalize_participant_name(value: str) -> str:
    return " ".join((value or "").strip().split())


def get_quiz_attempt_block_reason(quiz: GeneratedQuiz) -> str | None:
    if quiz.status == GeneratedQuiz.Status.APPROVED:
        return None
    return QUIZ_ATTEMPT_BLOCKED_STATUS_MESSAGES.get(
        quiz.status,
        "Quiz is not available for attempts in its current status.",
    )


def ensure_quiz_attempt_allowed(quiz: GeneratedQuiz) -> None:
    blocked_reason = get_quiz_attempt_block_reason(quiz)
    if blocked_reason is not None:
        raise DomainWorkflowError(blocked_reason)


def quiz_has_materialized_questions(quiz: GeneratedQuiz) -> bool:
    return quiz.questions.exists()


def build_attempt_form_questions(quiz: GeneratedQuiz) -> list[dict[str, Any]]:
    questions = quiz.questions.prefetch_related("choices").order_by("order", "id")
    prepared_questions: list[dict[str, Any]] = []
    for question_index, question in enumerate(questions):
        prepared_questions.append(
            {
                "question_id": question.id,
                "question_index": question_index,
                "order": question.order,
                "question_type": question.question_type,
                "prompt": question.prompt,
                "explanation": question.explanation,
                "choices": [
                    {
                        "choice_id": choice.id,
                        "choice_index": choice.order,
                        "text": choice.text,
                    }
                    for choice in question.choices.all().order_by("order", "id")
                ],
            }
        )
    return prepared_questions


def _extract_submitted_choice_info(
    question: Question,
    submitted_payload: dict[str, Any],
) -> tuple[int | None, str, str, bool]:
    selected_choice_id_raw = submitted_payload.get("selected_choice_id")
    selected_choice_id: int | None = None
    if selected_choice_id_raw not in (None, ""):
        try:
            selected_choice_id = int(selected_choice_id_raw)
        except (TypeError, ValueError):
            selected_choice_id = None

    choice_lookup = {choice.id: choice for choice in question.choices.all()}
    if selected_choice_id is not None:
        choice = choice_lookup.get(selected_choice_id)
        if choice is not None:
            submitted_text = (choice.text or "").strip()
            return choice.id, submitted_text, submitted_text, True

    legacy_choice_index = submitted_payload.get("selected_choice_index")
    if legacy_choice_index in (None, ""):
        legacy_choice_index = submitted_payload.get("choice_index")
    if legacy_choice_index in (None, ""):
        legacy_choice_index = submitted_payload.get("answer_index")

    if legacy_choice_index not in (None, ""):
        try:
            normalized_legacy_index = int(legacy_choice_index)
        except (TypeError, ValueError):
            normalized_legacy_index = None
        if normalized_legacy_index is not None:
            for choice in question.choices.all():
                if choice.order == normalized_legacy_index:
                    submitted_text = (choice.text or "").strip()
                    return choice.id, submitted_text, submitted_text, True

    submitted_text = (
        submitted_payload.get("selected_choice_text")
        or submitted_payload.get("answer")
        or submitted_payload.get("text_answer")
        or submitted_payload.get("text")
        or ""
    )
    submitted_text = str(submitted_text).strip()
    if submitted_text:
        matching_choice = next(
            (
                choice
                for choice in question.choices.all()
                if (choice.text or "").strip() == submitted_text
            ),
            None,
        )
        if matching_choice is not None:
            return matching_choice.id, submitted_text, submitted_text, True

    return None, submitted_text, submitted_text, bool(submitted_text)


def evaluate_quiz_answers(
    quiz: GeneratedQuiz,
    submitted_answers: list[dict[str, Any]],
) -> dict[str, Any]:
    questions = list(quiz.questions.prefetch_related("choices").order_by("order", "id"))
    if not questions:
        raise DomainWorkflowError("Cannot submit an attempt for an empty quiz.")

    answers_by_question_id: dict[int, dict[str, Any]] = {}
    answers_by_question_index: dict[int, dict[str, Any]] = {}

    for raw_answer in submitted_answers:
        if not isinstance(raw_answer, dict):
            continue
        question_id = raw_answer.get("question_id")
        if question_id not in (None, ""):
            try:
                answers_by_question_id[int(question_id)] = raw_answer
            except (TypeError, ValueError):
                pass
        question_index = raw_answer.get("question_index")
        if question_index not in (None, ""):
            try:
                answers_by_question_index[int(question_index)] = raw_answer
            except (TypeError, ValueError):
                pass

    results: list[dict[str, Any]] = []
    correct_answers = 0
    answered_questions = 0

    for question_index, question in enumerate(questions):
        submitted_payload = answers_by_question_id.get(question.id)
        if submitted_payload is None:
            submitted_payload = answers_by_question_index.get(question_index, {})

        selected_choice_id, submitted_answer, text_answer, answered = (
            _extract_submitted_choice_info(
                question,
                submitted_payload,
            )
        )

        correct_choice = next(
            (choice for choice in question.choices.all() if choice.is_correct), None
        )
        expected_answer = (
            correct_choice.text
            if correct_choice
            else question.correct_text_answer or ""
        ).strip()
        is_correct = bool(correct_choice and selected_choice_id == correct_choice.id)

        if answered:
            answered_questions += 1
        if is_correct:
            correct_answers += 1

        source_change_item = getattr(question, "source_change_item", None)
        source_heading = ""
        source_section_path = ""
        if source_change_item is not None:
            chunk = source_change_item.new_chunk or source_change_item.old_chunk
            if chunk is not None:
                source_heading = (chunk.heading or "").strip()
                source_section_path = (chunk.section_path or "").strip()

        results.append(
            {
                "question_id": question.id,
                "question_index": question_index,
                "question_order": question.order,
                "question": question.prompt,
                "question_type": question.question_type,
                "question_explanation": question.explanation,
                "source_change_item_id": (
                    source_change_item.id if source_change_item else None
                ),
                "source_heading": source_heading,
                "source_section_path": source_section_path,
                "selected_choice_id": selected_choice_id,
                "submitted_answer": submitted_answer,
                "text_answer": text_answer,
                "expected_answer": expected_answer,
                "is_correct": is_correct,
                "answered": answered,
            }
        )

    total_questions = len(questions)
    score_percent = (
        round((correct_answers / total_questions) * 100, 2) if total_questions else 0.0
    )

    return {
        "results": results,
        "score": correct_answers,
        "total_questions": total_questions,
        "answered_questions": answered_questions,
        "correct_answers": correct_answers,
        "score_percent": score_percent,
    }


@transaction.atomic
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
        locked_attempt.quiz.questions.prefetch_related("choices").order_by(
            "order", "id"
        )
    )
    if not questions:
        raise DomainWorkflowError(
            "Cannot submit an attempt for a quiz without materialized questions."
        )

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

    try:
        from .result_reporting import refresh_attempt_reporting_cache

        refresh_attempt_reporting_cache(locked_attempt)
    except Exception:
        logger.exception(
            "Attempt reporting cache refresh failed: attempt_id=%s",
            locked_attempt.id,
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
