from __future__ import annotations

import os
from typing import Iterable

from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue

from .models import Chunk

# Embeddings model (local)
from sentence_transformers import SentenceTransformer


_COLLECTION = "doc_chunks"
_MODEL_NAME = os.environ.get("EMBEDDINGS_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(_MODEL_NAME)
    return _model


def get_qdrant() -> QdrantClient:
    host = os.environ.get("QDRANT_HOST", "qdrant")
    port = int(os.environ.get("QDRANT_PORT", "6333"))
    return QdrantClient(host=host, port=port)


def ensure_collection(client: QdrantClient, vector_size: int) -> None:
    collections = client.get_collections().collections
    exists = any(c.name == _COLLECTION for c in collections)
    if exists:
        return

    client.create_collection(
        collection_name=_COLLECTION,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )


def embed_texts(texts: list[str]) -> list[list[float]]:
    model = get_model()
    vectors = model.encode(texts, normalize_embeddings=True)
    return vectors.tolist()


def index_chunks(version_id: int) -> int:
    """
    Index all chunks for a given version into Qdrant.
    point_id = chunk_id (stable).
    """
    client = get_qdrant()

    qs = Chunk.objects.filter(version_id=version_id).select_related("version__document")
    chunks = list(qs)
    if not chunks:
        return 0

    texts = [c.text for c in chunks]
    vectors = embed_texts(texts)
    vector_size = len(vectors[0])

    ensure_collection(client, vector_size)

    points: list[PointStruct] = []
    for c, vec in zip(chunks, vectors):
        points.append(
            PointStruct(
                id=c.id,
                vector=vec,
                payload={
                    "document_id": c.version.document_id,
                    "version_id": c.version_id,
                    "chunk_id": c.id,
                    "chunk_index": c.chunk_index,
                    "heading": c.heading,
                    "section_path": c.section_path,
                    "text": c.text,  # удобно для поиска без доп-запросов в БД
                },
            )
        )

    client.upsert(collection_name=_COLLECTION, points=points)
    return len(points)


def search_chunks(
    query: str,
    limit: int = 5,
    document_id: int | None = None,
    version_id: int | None = None,
) -> list[dict]:
    client = get_qdrant()

    qvec = embed_texts([query])[0]

    qfilter = None
    must = []
    if document_id is not None:
        must.append(
            FieldCondition(key="document_id", match=MatchValue(value=int(document_id)))
        )
    if version_id is not None:
        must.append(
            FieldCondition(key="version_id", match=MatchValue(value=int(version_id)))
        )
    if must:
        qfilter = Filter(must=must)

    # New API: query_points
    resp = client.query_points(
        collection_name=_COLLECTION,
        query=qvec,
        limit=limit,
        with_payload=True,
        query_filter=qfilter,
    )

    points = resp.points or []

    out: list[dict] = []
    for p in points:
        payload = p.payload or {}
        out.append(
            {
                "score": getattr(p, "score", None),
                "chunk_id": payload.get("chunk_id"),
                "document_id": payload.get("document_id"),
                "version_id": payload.get("version_id"),
                "chunk_index": payload.get("chunk_index"),
                "heading": payload.get("heading"),
                "section_path": payload.get("section_path"),
                "text": payload.get("text"),
            }
        )
    return out
