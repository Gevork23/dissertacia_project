from __future__ import annotations

from typing import Any

import numpy as np

from .embedder import Embedder


class SessionVectorStore:
    def __init__(
        self,
        chunks: list[dict[str, Any]],
        *,
        embedder: Embedder | None = None,
    ) -> None:
        self.chunks = chunks
        self.embedder = embedder or Embedder()
        self._matrix = np.zeros((0, 384), dtype=np.float32)
        self._index = None
        self._build()

    def _chunk_text(self, chunk: dict[str, Any]) -> str:
        heading = str(chunk.get("heading") or "")
        section_path = str(chunk.get("section_path") or "")
        text = str(chunk.get("text") or "")
        return "\n".join(part for part in [heading, section_path, text] if part)

    def _build(self) -> None:
        if not self.chunks:
            self._matrix = np.zeros((0, 384), dtype=np.float32)
            self._index = None
            return

        texts = [self._chunk_text(chunk) for chunk in self.chunks]
        self._matrix = self.embedder.encode(texts)

        try:
            import faiss
        except ImportError:  # pragma: no cover - env-dependent
            self._index = None
            return

        index = faiss.IndexFlatL2(self._matrix.shape[1])
        index.add(self._matrix)
        self._index = index

    def search(self, query: str, top_k: int = 5) -> list[tuple[dict[str, Any], float]]:
        if not self.chunks:
            return []

        query_vector = self.embedder.encode([query])
        limit = max(1, min(int(top_k), len(self.chunks)))

        if self._index is not None:
            distances, indexes = self._index.search(query_vector, limit)
            return [
                (self.chunks[int(idx)], float(distances[0][position]))
                for position, idx in enumerate(indexes[0])
                if int(idx) >= 0
            ]

        similarities = np.matmul(self._matrix, query_vector[0])
        ranked_indexes = np.argsort(similarities)[::-1][:limit]
        return [
            (self.chunks[int(idx)], float(1.0 - similarities[int(idx)]))
            for idx in ranked_indexes
        ]
