from django.urls import path

from .views import chat_api, chat_page

urlpatterns = [
    path("", chat_page, name="rag-chat"),
    path("api/", chat_api, name="rag-chat-api"),
]
