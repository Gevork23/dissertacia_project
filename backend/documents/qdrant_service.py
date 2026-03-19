from __future__ import annotations

import logging
import os
import re
import time
from typing import TYPE_CHECKING, Any

from django.db.models import Max
from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
    PointIdsList,
    PointStruct,
    VectorParams,
)

from .models import Chunk, DocumentVersion

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer
else:
    SentenceTransformer = Any

logger = logging.getLogger("documents.qdrant")

_COLLECTION = "doc_chunks"
_MODEL_NAME = os.environ.get(
    "EMBEDDINGS_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
)

_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        try:
            from sentence_transformers import (
                SentenceTransformer as _SentenceTransformer,
            )
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is not installed. "
                "Install backend/requirements-ml.txt to enable embeddings search."
            ) from exc

        started_at = time.perf_counter()
        _model = _SentenceTransformer(_MODEL_NAME)
        logger.info(
            "Embeddings model loaded: model=%s load_ms=%s",
            _MODEL_NAME,
            int((time.perf_counter() - started_at) * 1000),
        )
    return _model


def get_qdrant() -> QdrantClient:
    host = os.environ.get("QDRANT_HOST", "qdrant")
    port = int(os.environ.get("QDRANT_PORT", "6333"))
    timeout = float(os.environ.get("QDRANT_TIMEOUT_SECONDS", "3"))
    return QdrantClient(host=host, port=port, timeout=timeout)


def ensure_collection(client: QdrantClient, vector_size: int) -> None:
    started_at = time.perf_counter()
    collections = client.get_collections().collections
    exists = any(collection.name == _COLLECTION for collection in collections)

    if exists:
        logger.info(
            "Qdrant collection exists: name=%s check_ms=%s",
            _COLLECTION,
            int((time.perf_counter() - started_at) * 1000),
        )
        return

    client.create_collection(
        collection_name=_COLLECTION,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )
    logger.info(
        "Qdrant collection created: name=%s vector_size=%s create_ms=%s",
        _COLLECTION,
        vector_size,
        int((time.perf_counter() - started_at) * 1000),
    )


def build_embedding_text(chunk: Chunk) -> str:
    parts = []

    if chunk.heading:
        parts.append(chunk.heading)

    if chunk.section_path and chunk.section_path != chunk.heading:
        parts.append(chunk.section_path)

    parts.append(chunk.text)

    return "\n".join(part.strip() for part in parts if part and part.strip())


def embed_texts(texts: list[str]) -> list[list[float]]:
    model = get_model()
    started_at = time.perf_counter()
    vectors = model.encode(texts, normalize_embeddings=True)
    logger.info(
        "Embeddings created: count=%s ms=%s",
        len(texts),
        int((time.perf_counter() - started_at) * 1000),
    )
    return vectors.tolist()


def delete_version_points(client: QdrantClient, version_id: int) -> int:
    scroll_filter = Filter(
        must=[
            FieldCondition(
                key="version_id",
                match=MatchValue(value=int(version_id)),
            )
        ]
    )

    point_ids: list[int] = []
    offset = None

    while True:
        records, next_offset = client.scroll(
            collection_name=_COLLECTION,
            scroll_filter=scroll_filter,
            with_payload=False,
            with_vectors=False,
            limit=256,
            offset=offset,
        )
        point_ids.extend(int(record.id) for record in records if record.id is not None)

        if next_offset is None:
            break
        offset = next_offset

    if not point_ids:
        logger.info(
            "Qdrant cleanup skipped: no old points for version_id=%s", version_id
        )
        return 0

    client.delete(
        collection_name=_COLLECTION,
        points_selector=PointIdsList(points=point_ids),
        wait=True,
    )
    logger.info(
        "Qdrant cleanup done: version_id=%s deleted_points=%s",
        version_id,
        len(point_ids),
    )
    return len(point_ids)


def index_chunks(version_id: int) -> int:
    started_at = time.perf_counter()
    client = get_qdrant()

    queryset = Chunk.objects.filter(version_id=version_id).select_related(
        "version__document"
    )
    chunks = list(queryset)
    if not chunks:
        logger.warning("Index skipped: no chunks for version_id=%s", version_id)
        return 0

    logger.info("Index start: version_id=%s chunks=%s", version_id, len(chunks))

    texts = [build_embedding_text(chunk) for chunk in chunks]
    vectors = embed_texts(texts)
    vector_size = len(vectors[0])

    ensure_collection(client, vector_size)
    delete_version_points(client=client, version_id=version_id)

    points: list[PointStruct] = []
    for chunk, vector, embedding_text in zip(chunks, vectors, texts):
        points.append(
            PointStruct(
                id=chunk.id,
                vector=vector,
                payload={
                    "document_id": chunk.version.document_id,
                    "version_id": chunk.version_id,
                    "chunk_id": chunk.id,
                    "chunk_index": chunk.chunk_index,
                    "heading": chunk.heading,
                    "section_path": chunk.section_path,
                    "text": chunk.text,
                    "embedding_text": embedding_text,
                },
            )
        )

    upsert_started_at = time.perf_counter()
    client.upsert(collection_name=_COLLECTION, points=points, wait=True)

    logger.info(
        "Index done: version_id=%s points=%s upsert_ms=%s total_ms=%s",
        version_id,
        len(points),
        int((time.perf_counter() - upsert_started_at) * 1000),
        int((time.perf_counter() - started_at) * 1000),
    )
    return len(points)


def tokenize_query(query: str) -> list[str]:
    return [token.lower() for token in re.findall(r"\w+", query, flags=re.UNICODE)]


def get_latest_version_ids(document_id: int | None = None) -> list[int]:
    queryset = DocumentVersion.objects.all()

    if document_id is not None:
        queryset = queryset.filter(document_id=document_id)

    rows = queryset.values("document_id").annotate(latest_version=Max("version_number"))

    latest_ids: list[int] = []
    for row in rows:
        version = (
            DocumentVersion.objects.filter(
                document_id=row["document_id"],
                version_number=row["latest_version"],
            )
            .order_by("-id")
            .first()
        )
        if version is not None:
            latest_ids.append(version.id)

    return latest_ids


def lexical_bonus(query: str, payload: dict) -> float:
    query_lower = query.lower().strip()
    tokens = tokenize_query(query)

    heading = (payload.get("heading") or "").lower()
    section_path = (payload.get("section_path") or "").lower()
    text = (payload.get("text") or "").lower()

    bonus = 0.0

    if query_lower:
        if query_lower in heading:
            bonus += 0.35
        if query_lower in section_path:
            bonus += 0.25
        if query_lower in text:
            bonus += 0.60

    for token in tokens:
        if token in heading:
            bonus += 0.12
        if token in section_path:
            bonus += 0.08
        if token in text:
            bonus += 0.18

    if query_lower and "обязан" in query_lower:
        if "обязан" in text:
            bonus += 0.40
        if "обязанности" in heading or "обязанности" in section_path:
            bonus += 0.25

    return bonus


def build_result(point, query: str) -> dict:
    payload = point.payload or {}
    semantic_score = float(getattr(point, "score", 0.0) or 0.0)
    bonus = lexical_bonus(query=query, payload=payload)
    final_score = semantic_score + bonus

    return {
        "score": round(final_score, 6),
        "semantic_score": round(semantic_score, 6),
        "lexical_bonus": round(bonus, 6),
        "chunk_id": payload.get("chunk_id"),
        "document_id": payload.get("document_id"),
        "version_id": payload.get("version_id"),
        "chunk_index": payload.get("chunk_index"),
        "heading": payload.get("heading"),
        "section_path": payload.get("section_path"),
        "text": payload.get("text"),
    }


def deduplicate_results(results: list[dict]) -> list[dict]:
    seen_keys: set[tuple] = set()
    unique_results: list[dict] = []

    for item in results:
        key = (
            item.get("document_id"),
            item.get("version_id"),
            item.get("heading"),
            item.get("text"),
        )
        if key in seen_keys:
            continue
        seen_keys.add(key)
        unique_results.append(item)

    return unique_results


def search_chunks(
    query: str,
    limit: int = 5,
    document_id: int | None = None,
    version_id: int | None = None,
    latest_only: bool = True,
) -> list[dict]:
    started_at = time.perf_counter()
    client = get_qdrant()

    logger.info(
        "Search start: q=%r limit=%s document_id=%s version_id=%s latest_only=%s",
        query,
        limit,
        document_id,
        version_id,
        latest_only,
    )

    query_vector = embed_texts([query])[0]

    must_conditions = []

    if document_id is not None:
        must_conditions.append(
            FieldCondition(key="document_id", match=MatchValue(value=int(document_id)))
        )

    if version_id is not None:
        must_conditions.append(
            FieldCondition(key="version_id", match=MatchValue(value=int(version_id)))
        )
    elif latest_only:
        latest_ids = get_latest_version_ids(document_id=document_id)
        if latest_ids:
            must_conditions.append(
                FieldCondition(key="version_id", match=MatchAny(any=latest_ids))
            )

    query_filter = Filter(must=must_conditions) if must_conditions else None

    qdrant_started_at = time.perf_counter()
    response = client.query_points(
        collection_name=_COLLECTION,
        query=query_vector,
        limit=max(limit * 5, 20),
        with_payload=True,
        query_filter=query_filter,
    )

    points = response.points or []
    reranked = [build_result(point=point, query=query) for point in points]
    reranked.sort(
        key=lambda item: (
            item["score"],
            item["lexical_bonus"],
            item["semantic_score"],
        ),
        reverse=True,
    )

    results = deduplicate_results(reranked)[:limit]

    logger.info(
        "Search done: results=%s qdrant_ms=%s total_ms=%s",
        len(results),
        int((time.perf_counter() - qdrant_started_at) * 1000),
        int((time.perf_counter() - started_at) * 1000),
    )
    return results
