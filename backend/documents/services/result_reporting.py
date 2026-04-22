from __future__ import annotations

import hashlib
import json
import logging
from collections import Counter
from typing import Any

from django.conf import settings
from django.utils import timezone

from ..models import GeneratedQuiz, QuizAttempt
from .exceptions import DomainWorkflowError
from .llm_result_enhancer import (
    ResultLLMEnhancementError,
    get_default_result_llm_client,
)

logger = logging.getLogger("documents.result_reporting")

ATTEMPT_PROMPT_VERSION = "phase14-attempt-feedback-v1"
QUIZ_REPORT_PROMPT_VERSION = "phase14-quiz-report-v1"


def _round_percent(value: float) -> float:
    return round(float(value or 0.0), 2)


def get_pass_threshold_percent() -> int:
    return int(getattr(settings, "RESULT_PASS_THRESHOLD_PERCENT", 70))


def get_result_llm_model_name() -> str:
    configured_model = getattr(settings, "RESULT_LLM_MODEL", "").strip()
    return configured_model or "rule_based_fallback"


def _normalize_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _verdict_for_percent(score_percent: float) -> str:
    threshold = get_pass_threshold_percent()
    if score_percent >= threshold:
        if score_percent >= 90:
            return "Отличное усвоение изменений"
        if score_percent >= 80:
            return "Уверенное усвоение изменений"
        return "Порог успешного прохождения достигнут"
    if score_percent >= max(threshold - 15, 0):
        return "Нужна точечная доработка понимания изменений"
    return "Изменения усвоены недостаточно"


def _attempt_metrics(attempt: QuizAttempt) -> dict[str, Any]:
    if attempt.status != QuizAttempt.Status.COMPLETED:
        raise DomainWorkflowError(
            "Final result is available only for completed attempts."
        )

    unanswered_questions = max(attempt.total_questions - attempt.answered_questions, 0)
    wrong_answers = max(attempt.answered_questions - attempt.correct_answers, 0)
    threshold = get_pass_threshold_percent()
    passed = attempt.score_percent >= threshold

    return {
        "attempt_id": attempt.id,
        "quiz_id": attempt.quiz_id,
        "participant_name": attempt.participant_name,
        "attempt_status": attempt.status,
        "completion_status": "completed",
        "raw_score": attempt.score,
        "score_percent": _round_percent(attempt.score_percent),
        "total_questions": attempt.total_questions,
        "answered_questions": attempt.answered_questions,
        "correct_answers": attempt.correct_answers,
        "wrong_answers": wrong_answers,
        "unanswered_questions": unanswered_questions,
        "pass_threshold_percent": threshold,
        "passed": passed,
        "verdict": _verdict_for_percent(attempt.score_percent),
        "started_at": attempt.started_at,
        "submitted_at": attempt.submitted_at,
        "completed_at": attempt.completed_at,
        "answers": list(attempt.answers or []),
    }


def _build_rule_based_attempt_feedback(metrics: dict[str, Any]) -> str:
    incorrect = [
        item
        for item in metrics["answers"]
        if item.get("answered") and not item.get("is_correct")
    ]
    skipped = [item for item in metrics["answers"] if not item.get("answered")]
    weak_topics: list[str] = []
    for item in incorrect[:2] + skipped[:1]:
        topic = (
            item.get("source_heading")
            or item.get("source_section_path")
            or item.get("question")
        )
        topic = str(topic or "").strip()
        if topic and topic not in weak_topics:
            weak_topics.append(topic)

    if metrics["passed"]:
        intro = (
            f"Сотрудник прошёл тест: {metrics['correct_answers']} из {metrics['total_questions']} верно "
            f"({metrics['score_percent']}%)."
        )
    else:
        intro = (
            f"Сотрудник не достиг порога {metrics['pass_threshold_percent']}%: верно "
            f"{metrics['correct_answers']} из {metrics['total_questions']} ({metrics['score_percent']}%)."
        )

    if weak_topics:
        weak_part = (
            "Наибольшие затруднения связаны с: " + "; ".join(weak_topics[:3]) + "."
        )
    else:
        weak_part = (
            "Критических тематических провалов не выявлено по структуре ответов."
        )

    if skipped:
        recommendation = "Рекомендуется повторно изучить пропущенные вопросы и соответствующие фрагменты документа."
    elif incorrect:
        recommendation = "Рекомендуется повторно изучить фрагменты документа, по которым даны неверные ответы, и затем пройти тест повторно."
    else:
        recommendation = (
            "Можно переходить к следующему документу: все вопросы закрыты корректно."
        )

    return " ".join([intro, weak_part, recommendation]).strip()


def _build_rule_based_error_analysis(report_payload: dict[str, Any]) -> str:
    frequent_errors = report_payload.get("frequent_errors") or []
    if not frequent_errors:
        return "Типовые ошибки пока не выявлены: завершённых неверных ответов недостаточно для содержательного анализа."

    fragments = []
    for item in frequent_errors[:3]:
        title = (
            item.get("source_heading")
            or item.get("source_section_path")
            or item.get("question")
        )
        fragments.append(
            f"{title}: неверных ответов {item.get('wrong_count')} из {item.get('attempts_with_question')} наблюдений"
        )

    return (
        "Наиболее частые ошибки сосредоточены в следующих изменениях: "
        + "; ".join(fragments)
        + ". Это указывает на слабое понимание именно обновлённых норм, а не на случайные промахи."
    )


def _build_rule_based_manager_summary(report_payload: dict[str, Any]) -> str:
    attempts_count = report_payload.get("attempts_count", 0)
    if attempts_count == 0:
        return "Завершённых попыток пока нет, поэтому управленческий вывод по группе сотрудников сформировать нельзя."

    summary_parts = [
        f"По тесту завершено {attempts_count} попыток.",
        f"Средний результат группы — {report_payload.get('average_percentage', 0)}% при pass rate {report_payload.get('pass_rate', 0)}%.",
    ]
    frequent_errors = report_payload.get("frequent_errors") or []
    if frequent_errors:
        top_error = frequent_errors[0]
        topic = (
            top_error.get("source_heading")
            or top_error.get("source_section_path")
            or top_error.get("question")
        )
        summary_parts.append(f"Хуже всего усвоено изменение, связанное с: {topic}.")
    summary_parts.append(
        "Рекомендуется точечно повторить проблемные разделы документа и затем провести повторное контрольное прохождение."
    )
    return " ".join(summary_parts)


def _get_attempt_feedback_prompt(metrics: dict[str, Any]) -> tuple[str, str]:
    system_prompt = (
        "Ты выступаешь как строгий, краткий и прикладной методист по обучению сотрудников. "
        "Сформируй комментарий к результату попытки по-русски в 3-5 предложениях. "
        "Нужно объяснить: почему сотрудник справился или не справился, какие изменения документа вызвали трудности, "
        "и что повторно изучить. Не выдумывай факты, опирайся только на входные данные."
    )
    payload = {
        "prompt_version": ATTEMPT_PROMPT_VERSION,
        "participant_name": metrics["participant_name"],
        "score_percent": metrics["score_percent"],
        "pass_threshold_percent": metrics["pass_threshold_percent"],
        "passed": metrics["passed"],
        "correct_answers": metrics["correct_answers"],
        "wrong_answers": metrics["wrong_answers"],
        "unanswered_questions": metrics["unanswered_questions"],
        "answers": [
            {
                "question": item.get("question"),
                "source_heading": item.get("source_heading"),
                "source_section_path": item.get("source_section_path"),
                "question_explanation": item.get("question_explanation"),
                "submitted_answer": item.get("submitted_answer"),
                "expected_answer": item.get("expected_answer"),
                "is_correct": item.get("is_correct"),
                "answered": item.get("answered"),
            }
            for item in metrics["answers"]
        ],
    }
    user_prompt = (
        "Данные завершённой попытки:\n"
        + _normalize_json(payload)
        + "\n\nСформируй только итоговый комментарий без заголовка и без markdown."
    )
    return system_prompt, user_prompt


def _get_quiz_report_prompts(
    report_payload: dict[str, Any],
) -> tuple[tuple[str, str], tuple[str, str]]:
    analysis_system = (
        "Ты анализируешь типовые ошибки группы сотрудников по результатам теста по изменениям в нормативном документе. "
        "Сформируй 4-6 предложений по-русски: какие ошибки самые частые, как их можно сгруппировать по смыслу, "
        "и какие изменения документа поняты хуже всего."
    )
    manager_system = (
        "Ты готовишь краткий отчёт для руководителя о прохождении теста группой сотрудников. "
        "Сформируй 3-5 предложений по-русски без списков и markdown: средний результат, долю успешных прохождений, "
        "основную проблемную тему и практическую рекомендацию."
    )
    compact_payload = {
        "prompt_version": QUIZ_REPORT_PROMPT_VERSION,
        "quiz_title": report_payload["quiz"]["title"],
        "attempts_count": report_payload["attempts_count"],
        "average_percentage": report_payload["average_percentage"],
        "pass_rate": report_payload["pass_rate"],
        "frequent_errors": report_payload["frequent_errors"],
    }
    base = _normalize_json(compact_payload)
    analysis_user = (
        "Данные по группе сотрудников:\n"
        + base
        + "\n\nВыдай только аналитический текст без заголовка."
    )
    manager_user = (
        "Данные по группе сотрудников:\n"
        + base
        + "\n\nВыдай только управленческий summary без заголовка."
    )
    return (analysis_system, analysis_user), (manager_system, manager_user)


def _build_attempt_cache_key(attempt: QuizAttempt, metrics: dict[str, Any]) -> str:
    base = {
        "prompt_version": ATTEMPT_PROMPT_VERSION,
        "model": get_result_llm_model_name(),
        "attempt_id": attempt.id,
        "quiz_id": attempt.quiz_id,
        "participant_name": attempt.participant_name,
        "score": metrics["raw_score"],
        "score_percent": metrics["score_percent"],
        "answers": metrics["answers"],
    }
    return hashlib.sha256(_normalize_json(base).encode("utf-8")).hexdigest()


def _build_quiz_reporting_cache_key(
    quiz: GeneratedQuiz, report_payload: dict[str, Any]
) -> str:
    base = {
        "prompt_version": QUIZ_REPORT_PROMPT_VERSION,
        "model": get_result_llm_model_name(),
        "quiz_id": quiz.id,
        "attempts_count": report_payload["attempts_count"],
        "average_percentage": report_payload["average_percentage"],
        "frequent_errors": report_payload["frequent_errors"],
    }
    return hashlib.sha256(_normalize_json(base).encode("utf-8")).hexdigest()


def _generate_attempt_feedback(metrics: dict[str, Any]) -> tuple[str, str]:
    try:
        client = get_default_result_llm_client()
        system_prompt, user_prompt = _get_attempt_feedback_prompt(metrics)
        response = client.generate(system_prompt=system_prompt, user_prompt=user_prompt)
        return response.text, response.model
    except ResultLLMEnhancementError:
        logger.exception("Attempt LLM feedback generation failed.")
        return _build_rule_based_attempt_feedback(metrics), "rule_based_fallback"


def _generate_quiz_reporting_texts(
    report_payload: dict[str, Any],
) -> tuple[str, str, str]:
    try:
        client = get_default_result_llm_client()
        (analysis_system, analysis_user), (manager_system, manager_user) = (
            _get_quiz_report_prompts(report_payload)
        )
        analysis_response = client.generate(
            system_prompt=analysis_system, user_prompt=analysis_user
        )
        manager_response = client.generate(
            system_prompt=manager_system, user_prompt=manager_user
        )
        return analysis_response.text, manager_response.text, analysis_response.model
    except ResultLLMEnhancementError:
        logger.exception(
            "Quiz report LLM generation failed: quiz_id=%s",
            report_payload["quiz"]["id"],
        )
        return (
            _build_rule_based_error_analysis(report_payload),
            _build_rule_based_manager_summary(report_payload),
            "rule_based_fallback",
        )


def refresh_attempt_reporting_cache(attempt: QuizAttempt) -> QuizAttempt:
    attempt = QuizAttempt.objects.select_related("quiz").get(pk=attempt.pk)
    metrics = _attempt_metrics(attempt)
    cache_key = _build_attempt_cache_key(attempt, metrics)
    if attempt.llm_feedback and attempt.llm_feedback_cache_key == cache_key:
        refresh_quiz_reporting_cache(attempt.quiz)
        return attempt

    llm_feedback, llm_model = _generate_attempt_feedback(metrics)
    attempt.llm_feedback = llm_feedback
    attempt.llm_feedback_cache_key = cache_key
    attempt.llm_feedback_model = llm_model
    attempt.llm_feedback_generated_at = timezone.now()
    attempt.save(
        update_fields=[
            "llm_feedback",
            "llm_feedback_cache_key",
            "llm_feedback_model",
            "llm_feedback_generated_at",
        ]
    )
    refresh_quiz_reporting_cache(attempt.quiz)
    return attempt


def _build_frequent_errors(attempts: list[QuizAttempt]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for attempt in attempts:
        for item in attempt.answers or []:
            if not item.get("answered") or item.get("is_correct"):
                continue
            group_key = str(
                item.get("source_change_item_id")
                or item.get("question_id")
                or "unknown"
            )
            entry = grouped.setdefault(
                group_key,
                {
                    "group_key": group_key,
                    "question_id": item.get("question_id"),
                    "source_change_item_id": item.get("source_change_item_id"),
                    "question": item.get("question"),
                    "source_heading": item.get("source_heading"),
                    "source_section_path": item.get("source_section_path"),
                    "wrong_count": 0,
                    "attempts_with_question": 0,
                    "submitted_answers": Counter(),
                },
            )
            entry["wrong_count"] += 1
            entry["attempts_with_question"] += 1
            submitted_answer = str(item.get("submitted_answer") or "—").strip() or "—"
            entry["submitted_answers"][submitted_answer] += 1

    normalized = []
    for entry in grouped.values():
        normalized.append(
            {
                "group_key": entry["group_key"],
                "question_id": entry["question_id"],
                "source_change_item_id": entry["source_change_item_id"],
                "question": entry["question"],
                "source_heading": entry["source_heading"],
                "source_section_path": entry["source_section_path"],
                "wrong_count": entry["wrong_count"],
                "attempts_with_question": entry["attempts_with_question"],
                "common_wrong_answers": [
                    {"answer": answer, "count": count}
                    for answer, count in entry["submitted_answers"].most_common(3)
                ],
            }
        )
    normalized.sort(
        key=lambda item: (-item["wrong_count"], str(item.get("question") or ""))
    )
    return normalized[:5]


def refresh_quiz_reporting_cache(quiz: GeneratedQuiz) -> GeneratedQuiz:
    quiz = GeneratedQuiz.objects.get(pk=quiz.pk)
    report_payload = build_quiz_report_payload(quiz, ensure_llm=False)
    cache_key = _build_quiz_reporting_cache_key(quiz, report_payload)
    if (
        quiz.llm_error_analysis
        and quiz.llm_manager_summary
        and quiz.llm_reporting_cache_key == cache_key
    ):
        return quiz

    llm_error_analysis, llm_manager_summary, llm_model = _generate_quiz_reporting_texts(
        report_payload
    )
    quiz.llm_error_analysis = llm_error_analysis
    quiz.llm_manager_summary = llm_manager_summary
    quiz.llm_reporting_cache_key = cache_key
    quiz.llm_reporting_model = llm_model
    quiz.llm_reporting_generated_at = timezone.now()
    quiz.save(
        update_fields=[
            "llm_error_analysis",
            "llm_manager_summary",
            "llm_reporting_cache_key",
            "llm_reporting_model",
            "llm_reporting_generated_at",
        ]
    )
    return quiz


def build_quiz_report_payload(
    quiz: GeneratedQuiz, *, ensure_llm: bool = True
) -> dict[str, Any]:
    attempts = list(
        quiz.attempts.filter(status=QuizAttempt.Status.COMPLETED).order_by(
            "-submitted_at", "-created_at"
        )
    )
    attempts_count = len(attempts)
    scores = [attempt.score for attempt in attempts]
    percentages = [attempt.score_percent for attempt in attempts]
    pass_threshold = get_pass_threshold_percent()
    passed_count = sum(
        1 for attempt in attempts if attempt.score_percent >= pass_threshold
    )
    average_score = round(sum(scores) / attempts_count, 2) if attempts_count else 0.0
    average_percentage = (
        round(sum(percentages) / attempts_count, 2) if attempts_count else 0.0
    )
    pass_rate = (
        round((passed_count / attempts_count) * 100, 2) if attempts_count else 0.0
    )
    frequent_errors = _build_frequent_errors(attempts)

    from ..api.serializers import GeneratedQuizSerializer, QuizAttemptSerializer

    base_payload = {
        "quiz": GeneratedQuizSerializer(quiz).data,
        "attempts_count": attempts_count,
        "average_score": average_score,
        "average_percentage": average_percentage,
        "best_score": max(scores) if scores else 0,
        "pass_rate": pass_rate,
        "pass_threshold_percent": pass_threshold,
        "latest_attempts": QuizAttemptSerializer(attempts[:10], many=True).data,
        "frequent_errors": frequent_errors,
    }

    if ensure_llm:
        quiz = refresh_quiz_reporting_cache(quiz)
    base_payload["llm_error_analysis"] = quiz.llm_error_analysis
    base_payload["llm_manager_summary"] = quiz.llm_manager_summary
    return base_payload


def build_attempt_result_payload(
    attempt: QuizAttempt, *, ensure_llm: bool = True
) -> dict[str, Any]:
    attempt = QuizAttempt.objects.select_related("quiz").get(pk=attempt.pk)
    metrics = _attempt_metrics(attempt)
    if ensure_llm:
        attempt = refresh_attempt_reporting_cache(attempt)
    report_payload = build_quiz_report_payload(attempt.quiz, ensure_llm=ensure_llm)
    metrics.update(
        {
            "llm_feedback": attempt.llm_feedback,
            "llm_error_analysis": report_payload["llm_error_analysis"],
            "llm_manager_summary": report_payload["llm_manager_summary"],
            "quiz_report": {
                "attempts_count": report_payload["attempts_count"],
                "average_score": report_payload["average_score"],
                "average_percentage": report_payload["average_percentage"],
                "best_score": report_payload["best_score"],
                "pass_rate": report_payload["pass_rate"],
                "pass_threshold_percent": report_payload["pass_threshold_percent"],
                "frequent_errors": report_payload["frequent_errors"],
            },
        }
    )
    return metrics
