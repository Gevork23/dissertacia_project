from __future__ import annotations

import json
from typing import Any

from django.conf import settings

GROUNDED_SYSTEM_PROMPT = (
    "You are a helpful assistant. Answer the user's question based strictly on the provided documents. "
    "Respond in Russian. If the answer is not in the documents, say so clearly. "
    "Do not output JSON. Provide only natural language answer."
)


class GeneratorUnavailableError(RuntimeError):
    """Raised when Ollama or the selected model cannot be used."""


class VikhrGenerator:
    def __init__(self, model: str | None = None) -> None:
        self.model = model or settings.RAG_OLLAMA_MODEL

    def _chat(self, *, messages: list[dict[str, Any]], options: dict[str, Any]) -> str:
        try:
            import ollama
        except ImportError as exc:  # pragma: no cover - env-dependent
            raise GeneratorUnavailableError(
                "Ollama client is unavailable. Install the `ollama` Python package."
            ) from exc

        try:
            response = ollama.chat(
                model=self.model,
                messages=messages,
                options=options,
            )
        except Exception as exc:  # pragma: no cover - env-dependent
            raise GeneratorUnavailableError(
                "Генератор временно недоступен. Проверьте, что Ollama запущена и "
                f"модель `{self.model}` загружена."
            ) from exc

        message = response.get("message") or {}
        content = str(message.get("content") or "").strip()
        if not content:
            raise GeneratorUnavailableError("Генератор вернул пустой ответ.")
        return content

    def generate(
        self,
        messages: list[dict[str, Any]],
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> str:
        options = {
            "temperature": temperature,
            "num_predict": max_tokens,
        }
        try:
            return self._chat(messages=messages, options=options)
        except GeneratorUnavailableError:
            raise
        except Exception:
            raise

    def build_messages(
        self,
        *,
        question: str,
        documents_list: list[dict[str, Any]],
    ) -> list[dict[str, str]]:
        # Формируем читаемое представление документов
        docs_text_parts = []
        for doc in documents_list:
            docs_text_parts.append(
                f"=== Документ {doc['doc_id']}: {doc['title']} ===\n{doc['content']}"
            )
        docs_block = "\n\n".join(docs_text_parts)

        full_prompt = (
            f"Ты помощник, который отвечает на вопросы строго по предоставленным документам.\n\n"
            f"Документы:\n{docs_block}\n\n"
            f"Вопрос: {question}\n\n"
            f"Ответь на русском языке, используя только эти документы. Если ответа нет в документах, так и скажи."
        )

        return [
            {"role": "system", "content": "Ты полезный ассистент. Отвечай только по предоставленным документам."},
            {"role": "user", "content": full_prompt},
        ]

    def generate_grounded_answer(
        self,
        *,
        question: str,
        documents_list: list[dict[str, Any]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        messages = self.build_messages(
            question=question,
            documents_list=documents_list,
        )
        try:
            return self.generate(
                messages=messages,
                temperature=temperature
                if temperature is not None
                else settings.RAG_TEMPERATURE,
                max_tokens=max_tokens if max_tokens is not None else settings.RAG_MAX_TOKENS,
            )
        except GeneratorUnavailableError:
            fallback_messages = [
                {"role": "system", "content": GROUNDED_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Documents:\n"
                        f"{json.dumps(documents_list, ensure_ascii=False)}\n\n"
                        f"Question: {question}"
                    ),
                },
            ]
            return self.generate(
                messages=fallback_messages,
                temperature=temperature
                if temperature is not None
                else settings.RAG_TEMPERATURE,
                max_tokens=max_tokens if max_tokens is not None else settings.RAG_MAX_TOKENS,
            )
