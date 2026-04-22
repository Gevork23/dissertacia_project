from __future__ import annotations

import json
from dataclasses import dataclass
from urllib import error, request

from django.conf import settings


class ResultLLMEnhancementError(Exception):
    pass


@dataclass(frozen=True)
class ResultLLMResponse:
    text: str
    model: str


class OllamaResultLLMClient:
    def __init__(self) -> None:
        self.api_url = getattr(
            settings,
            "RESULT_LLM_API_URL",
            "http://127.0.0.1:11434/api/generate",
        )
        self.model = getattr(settings, "RESULT_LLM_MODEL", "")
        self.timeout = getattr(settings, "RESULT_LLM_TIMEOUT_SECONDS", 60)
        self.temperature = getattr(settings, "RESULT_LLM_TEMPERATURE", 0)
        self.seed = getattr(settings, "RESULT_LLM_SEED", 42)
        self.enabled = bool(getattr(settings, "RESULT_LLM_ENABLED", False))

    def ensure_ready(self) -> None:
        if not self.enabled:
            raise ResultLLMEnhancementError("RESULT_LLM_ENABLED is disabled.")
        if not self.model:
            raise ResultLLMEnhancementError("RESULT_LLM_MODEL is not configured.")
        if not self.api_url:
            raise ResultLLMEnhancementError("RESULT_LLM_API_URL is not configured.")

    def generate(self, *, system_prompt: str, user_prompt: str) -> ResultLLMResponse:
        self.ensure_ready()

        payload = {
            "model": self.model,
            "system": system_prompt,
            "prompt": user_prompt,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "seed": self.seed,
            },
        }
        body = json.dumps(payload).encode("utf-8")
        http_request = request.Request(
            self.api_url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with request.urlopen(http_request, timeout=self.timeout) as response:
                raw_response = response.read().decode("utf-8")
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise ResultLLMEnhancementError(
                f"LLM HTTP error {exc.code}: {body}"
            ) from exc
        except error.URLError as exc:
            raise ResultLLMEnhancementError(f"LLM network error: {exc}") from exc

        try:
            parsed = json.loads(raw_response)
        except json.JSONDecodeError as exc:
            raise ResultLLMEnhancementError(
                "Failed to parse LLM response JSON."
            ) from exc

        generated_text = str(parsed.get("response") or "").strip()
        if not generated_text:
            raise ResultLLMEnhancementError("LLM response is empty.")

        return ResultLLMResponse(text=generated_text, model=self.model)


def get_default_result_llm_client() -> OllamaResultLLMClient:
    return OllamaResultLLMClient()
