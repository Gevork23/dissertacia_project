from django.urls import path

from .demo_views import (
    approve_quiz_view,
    attempt_detail,
    compare_page,
    create_quiz,
    dashboard,
    document_detail,
    quiz_detail,
    quizzes_page,
    report_page,
    take_quiz,
)

urlpatterns = [
    path("", dashboard, name="demo-dashboard"),
    path("documents/<int:document_id>/", document_detail, name="demo-document-detail"),
    path("compare/", compare_page, name="demo-compare"),
    path("compare/create-quiz/", create_quiz, name="demo-create-quiz"),
    path("quizzes/", quizzes_page, name="demo-quizzes"),
    path("quizzes/<int:quiz_id>/", quiz_detail, name="demo-quiz-detail"),
    path(
        "quizzes/<int:quiz_id>/approve/",
        approve_quiz_view,
        name="demo-approve-quiz",
    ),
    path("quizzes/<int:quiz_id>/take/", take_quiz, name="demo-take-quiz"),
    path("quizzes/<int:quiz_id>/report/", report_page, name="demo-report"),
    path("attempts/<int:attempt_id>/", attempt_detail, name="demo-attempt-detail"),
]
