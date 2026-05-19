from __future__ import annotations

import threading
from typing import Iterable

import numpy as np
from django.conf import settings

_MODEL_LOCK = threading.Lock()
_MODEL_INSTANCE = None


class EmbedderUnavailableError(RuntimeError):
    """Raised when the embedding backend cannot be initialized."""


def _normalize_rows(matrix: np.ndarray) -> np.ndarray:
    if matrix.size == 0:
        return matrix
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms = np.where(norms == 0.0, 1.0, norms)
    return matrix / norms


class Embedder:
    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or settings.RAG_EMBEDDER_MODEL
        self._model = None

    def _load_model(self):
        global _MODEL_INSTANCE
        if _MODEL_INSTANCE is not None:
            return _MODEL_INSTANCE

        with _MODEL_LOCK:
            if _MODEL_INSTANCE is not None:
                return _MODEL_INSTANCE
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:  # pragma: no cover - env-dependent
                raise EmbedderUnavailableError(
                    "Embedding model is unavailable. Install sentence-transformers."
                ) from exc

            _MODEL_INSTANCE = SentenceTransformer(self.model_name)
        return _MODEL_INSTANCE

    def encode(self, texts: list[str] | Iterable[str]) -> np.ndarray:
        text_list = [str(text or "") for text in texts]
        if not text_list:
            return np.zeros((0, 384), dtype=np.float32)

        model = self._model or self._load_model()
        self._model = model
        vectors = model.encode(
            text_list,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        array = np.asarray(vectors, dtype=np.float32)
        return _normalize_rows(array)
