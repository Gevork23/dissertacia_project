from django.urls import path
from rest_framework.routers import DefaultRouter

from .api import (
    compare_versions,
    compare_versions_brief,
    compare_versions_quiz,
    list_quiz_attempts,
    list_saved_quizzes,
    save_versions_quiz,
    search,
    submit_quiz_attempt,
)
from .views import DocumentVersionViewSet, DocumentViewSet

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
        "quizzes/<int:quiz_id>/attempts/",
        list_quiz_attempts,
        name="list-quiz-attempts",
    ),
    path(
        "quizzes/<int:quiz_id>/attempts/submit/",
        submit_quiz_attempt,
        name="submit-quiz-attempt",
    ),
] + router.urls
