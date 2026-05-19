from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from documents.models import Document
from documents.services.versioning import create_text_document_version


class RagViewsTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.get(username="admin")
        self.client.force_login(self.admin_user)

        document = Document.objects.create(title="RAG demo document", description="")
        self.version_one = create_text_document_version(
            document=document,
            source_filename="v1.txt",
            raw_text=(
                "Статья 1 Срок\n"
                "1. Срок рассмотрения заявления составляет 10 рабочих дней."
            ),
        )
        self.version_two = create_text_document_version(
            document=document,
            source_filename="v2.txt",
            raw_text=(
                "Статья 1 Срок\n"
                "1. Срок рассмотрения заявления составляет 7 рабочих дней."
            ),
        )

    def test_compare_page_populates_rag_session_chunks(self):
        response = self.client.get(
            reverse("demo-compare"),
            {
                "from_version": self.version_one.id,
                "to_version": self.version_two.id,
            },
        )

        self.assertEqual(response.status_code, 200)
        session = self.client.session
        self.assertIn("rag_chunks", session)
        self.assertGreater(len(session["rag_chunks"]), 0)

    def test_chat_page_is_available(self):
        response = self.client.get(reverse("rag-chat"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "RAG Chat")

    @patch("rag.views.answer_question")
    def test_chat_api_returns_answer_and_persists_history(self, answer_question_mock):
        session = self.client.session
        session["rag_chunks"] = [
            {
                "chunk_id": "1:1",
                "text": "Срок рассмотрения заявления составляет 7 рабочих дней.",
                "heading": "Статья 1",
                "section_path": "Статья 1",
                "document_title": "RAG demo document",
                "version_label": "v2",
            }
        ]
        session.save()

        answer_question_mock.return_value = {
            "question": "Какие сроки изменились?",
            "answer": "Срок рассмотрения заявления сокращён до 7 рабочих дней.",
            "sources": [
                {
                    "doc_id": 1,
                    "chunk_id": "1:1",
                    "title": "RAG demo document | v2 | Статья 1",
                    "text": "Срок рассмотрения заявления составляет 7 рабочих дней.",
                    "score": 0.01,
                }
            ],
        }

        response = self.client.post(
            reverse("rag-chat-api"),
            content_type="application/json",
            data='{"action":"ask","question":"Какие сроки изменились?"}',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(len(payload["history"]), 1)
        self.assertEqual(
            self.client.session["chat_history"][0]["answer"],
            "Срок рассмотрения заявления сокращён до 7 рабочих дней.",
        )

    def test_chat_api_clear_action_empties_history(self):
        session = self.client.session
        session["chat_history"] = [{"question": "Q", "answer": "A", "sources": []}]
        session.save()

        response = self.client.post(
            reverse("rag-chat-api"),
            content_type="application/json",
            data='{"action":"clear"}',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["history"], [])
