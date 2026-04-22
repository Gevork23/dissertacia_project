from django.urls import path
from rest_framework.routers import DefaultRouter

from .endpoints import (
    approve_quiz,
    compare_versions,
    compare_versions_brief,
    compare_versions_quiz,
    list_quiz_attempts,
    start_quiz_attempt_view,
    list_saved_quizzes,
    quiz_report,
    reject_quiz,
    save_versions_quiz,
    search,
    submit_quiz_attempt,
    submit_quiz_review,
)
from .viewsets import DocumentVersionViewSet, DocumentViewSet

router = DefaultRouter()
router.register("documents", DocumentViewSet, basename="documents")
router.register("versions", DocumentVersionViewSet, basename="versions")

urlpatterns = [
    path("search/", search, name="search"),
    path("compare/", compare_versions, name="compare-versions"),
    path("compare/brief/", compare_versions_brief, name="compare-versions-brief"),
    path("compare/quiz/", compare_versions_quiz, name="compare-versions-quiz"),
    path("compare/quiz/save/", save_versions_quiz, name="save-versions-quiz"),
    path("quizzes/", list_saved_quizzes, name="list-saved-quizzes"),
    path(
        "quizzes/<int:quiz_id>/submit-review/",
        submit_quiz_review,
        name="submit-quiz-review",
    ),
    path("quizzes/<int:quiz_id>/approve/", approve_quiz, name="approve-quiz"),
    path("quizzes/<int:quiz_id>/reject/", reject_quiz, name="reject-quiz"),
    path("quizzes/<int:quiz_id>/report/", quiz_report, name="quiz-report"),
    path(
        "quizzes/<int:quiz_id>/attempts/",
        list_quiz_attempts,
        name="list-quiz-attempts",
    ),
    path(
        "quizzes/<int:quiz_id>/attempts/start/",
        start_quiz_attempt_view,
        name="start-quiz-attempt",
    ),
    path(
        "quizzes/<int:quiz_id>/attempts/submit/",
        submit_quiz_attempt,
        name="submit-quiz-attempt",
    ),
] + router.urls
