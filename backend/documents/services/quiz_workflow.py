from __future__ import annotations

from django.utils import timezone

from ..models import GeneratedQuiz
from .exceptions import DomainWorkflowError

QUIZ_ATTEMPT_BLOCKED_STATUS_MESSAGES = {
    GeneratedQuiz.Status.DRAFT: "Quiz is still a draft and must be submitted for review first.",
    GeneratedQuiz.Status.PENDING_REVIEW: "Quiz is pending review and cannot be assigned yet.",
    GeneratedQuiz.Status.REJECTED: "Rejected quiz cannot be assigned until it is resubmitted and approved.",
    GeneratedQuiz.Status.SUPERSEDED: "Superseded quiz cannot be assigned because a newer quiz replaced it.",
    GeneratedQuiz.Status.ARCHIVED: "Archived quiz cannot be assigned.",
}


def quiz_has_materialized_questions(quiz: GeneratedQuiz) -> bool:
    """Return True when a generated quiz has persisted Question rows."""
    return quiz.questions.exists()


def ensure_quiz_can_enter_review(quiz: GeneratedQuiz) -> None:
    """Validate that a quiz is materialized before entering review lifecycle."""
    if quiz.questions_count <= 0 or not quiz_has_materialized_questions(quiz):
        raise DomainWorkflowError(
            "Quiz must contain materialized questions before it can enter the approval workflow."
        )


def get_quiz_attempt_block_reason(quiz: GeneratedQuiz) -> str | None:
    """Return a human-readable reason why employees cannot start/submit attempts."""
    if quiz.status != GeneratedQuiz.Status.APPROVED:
        return QUIZ_ATTEMPT_BLOCKED_STATUS_MESSAGES.get(
            quiz.status,
            "Quiz must be approved before it can be assigned.",
        )
    if quiz.questions_count <= 0 or not quiz_has_materialized_questions(quiz):
        return "Cannot submit an attempt for an empty quiz."
    return None


def ensure_quiz_attempt_allowed(quiz: GeneratedQuiz) -> None:
    """Raise when a quiz cannot be assigned to an employee attempt."""
    reason = get_quiz_attempt_block_reason(quiz)
    if reason is not None:
        raise DomainWorkflowError(reason)


def submit_quiz_for_review(quiz: GeneratedQuiz) -> GeneratedQuiz:
    """Move a materialized draft/rejected quiz into reviewer approval flow."""
    if quiz.status not in {GeneratedQuiz.Status.DRAFT, GeneratedQuiz.Status.REJECTED}:
        raise DomainWorkflowError(
            f"Quiz in status '{quiz.status}' cannot be submitted for review."
        )

    ensure_quiz_can_enter_review(quiz)

    quiz.status = GeneratedQuiz.Status.PENDING_REVIEW
    quiz.submitted_for_review_at = timezone.now()
    quiz.rejected_by_name = ""
    quiz.rejected_at = None
    quiz.rejection_comment = ""
    quiz.save(
        update_fields=[
            "status",
            "submitted_for_review_at",
            "rejected_by_name",
            "rejected_at",
            "rejection_comment",
            "updated_at",
        ]
    )
    return quiz


def approve_generated_quiz(
    *,
    quiz: GeneratedQuiz,
    approved_by_name: str,
    approval_comment: str = "",
) -> GeneratedQuiz:
    """Approve a quiz that is waiting for review."""
    approved_by_name = (approved_by_name or "").strip()
    if not approved_by_name:
        raise DomainWorkflowError("Field 'approved_by_name' is required.")
    if quiz.status != GeneratedQuiz.Status.PENDING_REVIEW:
        raise DomainWorkflowError(f"Quiz in status '{quiz.status}' cannot be approved.")

    ensure_quiz_can_enter_review(quiz)

    quiz.status = GeneratedQuiz.Status.APPROVED
    quiz.approved_by_name = approved_by_name
    quiz.approved_at = timezone.now()
    quiz.approval_comment = (approval_comment or "").strip()
    quiz.save(
        update_fields=[
            "status",
            "approved_by_name",
            "approved_at",
            "approval_comment",
            "updated_at",
        ]
    )
    return quiz


def reject_generated_quiz(
    *,
    quiz: GeneratedQuiz,
    rejected_by_name: str,
    rejection_comment: str = "",
) -> GeneratedQuiz:
    """Reject a quiz that is waiting for review."""
    rejected_by_name = (rejected_by_name or "").strip()
    if not rejected_by_name:
        raise DomainWorkflowError("Field 'rejected_by_name' is required.")
    if quiz.status != GeneratedQuiz.Status.PENDING_REVIEW:
        raise DomainWorkflowError(f"Quiz in status '{quiz.status}' cannot be rejected.")

    quiz.status = GeneratedQuiz.Status.REJECTED
    quiz.rejected_by_name = rejected_by_name
    quiz.rejected_at = timezone.now()
    quiz.rejection_comment = (rejection_comment or "").strip()
    quiz.save(
        update_fields=[
            "status",
            "rejected_by_name",
            "rejected_at",
            "rejection_comment",
            "updated_at",
        ]
    )
    return quiz


def mark_quiz_superseded(quiz: GeneratedQuiz, *, reason: str = "") -> GeneratedQuiz:
    """Mark an older quiz as replaced by a newer generated quiz."""
    if quiz.status in {GeneratedQuiz.Status.SUPERSEDED, GeneratedQuiz.Status.ARCHIVED}:
        return quiz

    quiz.status = GeneratedQuiz.Status.SUPERSEDED
    quiz.superseded_at = timezone.now()
    quiz.superseded_reason = (reason or "").strip()
    quiz.save(
        update_fields=[
            "status",
            "superseded_at",
            "superseded_reason",
            "updated_at",
        ]
    )
    return quiz
