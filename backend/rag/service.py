from __future__ import annotations

from importlib import import_module
from typing import Any

from django.conf import settings

from .embedder import EmbedderUnavailableError
from .generator import GeneratorUnavailableError, VikhrGenerator
from .vector_store import SessionVectorStore


class RagServiceError(RuntimeError):
    """Raised when the RAG pipeline cannot answer the question."""


def _session_store():
    engine = import_module(settings.SESSION_ENGINE)
    return engine.SessionStore


def load_session_data(session_key: str) -> dict[str, Any]:
    if not session_key:
        raise RagServiceError("Сессия не найдена.")

    session = _session_store()(session_key=session_key)
    if not session.exists(session.session_key):
        raise RagServiceError("Сессия не найдена.")
    return dict(session.load())


def _make_documents_list(
    results: list[tuple[dict[str, Any], float]],
) -> list[dict[str, Any]]:
    documents_list: list[dict[str, Any]] = []
    for index, (chunk, score) in enumerate(results, start=1):
        title_parts = [
            str(chunk.get("document_title") or ""),
            str(chunk.get("version_label") or ""),
            str(chunk.get("heading") or chunk.get("section_path") or ""),
        ]
        title = " | ".join(part for part in title_parts if part)
        documents_list.append(
            {
                "doc_id": index,
                "title": title or f"Chunk {index}",
                "content": str(chunk.get("text") or ""),
                "chunk_id": chunk.get("chunk_id"),
                "score": score,
            }
        )
    return documents_list


def answer_question(question: str, session_key: str) -> dict[str, Any]:
    normalized_question = str(question or "").strip()
    if not normalized_question:
        raise RagServiceError("Введите вопрос.")

    session_data = load_session_data(session_key)
    chunks = session_data.get("rag_chunks") or []
    if not isinstance(chunks, list) or not chunks:
        raise RagServiceError(
            "Нет загруженных документов. "
            "Сначала выполните сравнение через /compare/ или /visualize/."
        )

    try:
        vector_store = SessionVectorStore(chunks)
        search_results = vector_store.search(
            normalized_question,
            top_k=settings.RAG_TOP_K,
        )
    except EmbedderUnavailableError as exc:
        raise RagServiceError(str(exc)) from exc

    if not search_results:
        raise RagServiceError("Не удалось найти подходящие фрагменты для ответа.")

    documents_list = _make_documents_list(search_results)

    try:
        answer = VikhrGenerator().generate_grounded_answer(
            question=normalized_question,
            documents_list=documents_list,
            temperature=settings.RAG_TEMPERATURE,
            max_tokens=settings.RAG_MAX_TOKENS,
        )
    except GeneratorUnavailableError as exc:
        raise RagServiceError(str(exc)) from exc

    sources = []
    for document in documents_list:
        sources.append(
            {
                "doc_id": document["doc_id"],
                "chunk_id": document.get("chunk_id"),
                "title": document["title"],
                "text": document["content"],
                "score": float(document.get("score", 0.0)),
            }
        )

    return {
        "question": normalized_question,
        "answer": answer,
        "sources": sources,
    }
