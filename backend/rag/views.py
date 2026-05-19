from __future__ import annotations

import json
from typing import Any

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods

from .service import RagServiceError, answer_question


def _session_history(request: HttpRequest) -> list[dict[str, Any]]:
    history = request.session.get("chat_history") or []
    if not isinstance(history, list):
        history = []
    return history


@require_GET
@login_required
def chat_page(request: HttpRequest):
    request.session.setdefault("chat_history", [])
    request.session.modified = True
    return render(
        request,
        "rag/chat.html",
        {
            "chat_history": _session_history(request),
            "has_rag_chunks": bool(request.session.get("rag_chunks")),
        },
    )


@require_http_methods(["POST"])
@ensure_csrf_cookie
@login_required
def chat_api(request: HttpRequest) -> JsonResponse:
    if not request.session.session_key:
        request.session.create()

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

    action = str(data.get("action", "ask")).strip().lower()

    if action == "clear":
        request.session["chat_history"] = []
        request.session.pop("rag_chunks", None)
        request.session.modified = True
        return JsonResponse({"ok": True, "history": []})

    if action != "ask":
        return JsonResponse({"ok": False, "error": "Unknown action"}, status=400)

    question = str(data.get("question", "")).strip()
    if not question:
        return JsonResponse({"ok": False, "error": "Введите вопрос."}, status=400)

    try:
        result = answer_question(question, request.session.session_key)
    except RagServiceError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    history = _session_history(request)
    history.append(result)
    request.session["chat_history"] = history
    request.session.modified = True

    return JsonResponse({"ok": True, "history": history})
