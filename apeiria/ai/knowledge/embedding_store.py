"""File-backed storage for default knowledge chunk embeddings."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from apeiria.db.runtime import database_runtime
from apeiria.utils.files import atomic_write_text

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class ChunkEmbeddingRecord:
    """Stored embedding payload for one knowledge chunk."""

    chunk_id: str
    embedding_model: str
    vector: list[float]
    updated_at: str
    embedding_space_id: str | None = None
    dimension: int | None = None
    content_hash: str | None = None


def _storage_dir() -> Path:
    return database_runtime.project_root / "data" / "ai" / "knowledge_chunk_embeddings"


def _record_path(chunk_id: str) -> Path:
    safe_chunk_id = chunk_id.replace("/", "_").replace("\\", "_")
    return _storage_dir() / f"{safe_chunk_id}.json"


def _utcnow_text() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ChunkEmbeddingStore:
    """Read and write knowledge chunk embedding payloads outside SQLite."""

    def upsert(
        self,
        *,
        chunk_id: str,
        embedding_model: str,
        vector: list[float],
        embedding_space_id: str | None = None,
        content_hash: str | None = None,
    ) -> ChunkEmbeddingRecord:
        record = ChunkEmbeddingRecord(
            chunk_id=chunk_id,
            embedding_model=embedding_model,
            vector=vector,
            updated_at=_utcnow_text(),
            embedding_space_id=embedding_space_id,
            dimension=len(vector),
            content_hash=content_hash,
        )
        atomic_write_text(
            _record_path(chunk_id),
            json.dumps(
                {
                    "chunk_id": record.chunk_id,
                    "embedding_model": record.embedding_model,
                    "embedding_space_id": record.embedding_space_id,
                    "dimension": record.dimension,
                    "content_hash": record.content_hash,
                    "vector": record.vector,
                    "updated_at": record.updated_at,
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
        )
        return record

    def get(self, *, chunk_id: str) -> ChunkEmbeddingRecord | None:
        target = _record_path(chunk_id)
        if not target.is_file():
            return None
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return self._record_from_payload(chunk_id=chunk_id, payload=payload)

    def delete(self, *, chunk_id: str) -> bool:
        target = _record_path(chunk_id)
        try:
            target.unlink()
        except FileNotFoundError:
            return False
        return True

    def _record_from_payload(
        self,
        *,
        chunk_id: str,
        payload: object,
    ) -> ChunkEmbeddingRecord | None:
        if not isinstance(payload, dict):
            return None
        embedding_model = payload.get("embedding_model")
        embedding_space_id = payload.get("embedding_space_id")
        dimension = payload.get("dimension")
        content_hash = payload.get("content_hash")
        vector = payload.get("vector")
        updated_at = payload.get("updated_at")
        if not isinstance(embedding_model, str):
            return None
        if not isinstance(updated_at, str):
            updated_at = _utcnow_text()
        if not isinstance(vector, list):
            return None
        numeric_vector = [
            float(value) for value in vector if isinstance(value, (int, float))
        ]
        if not numeric_vector:
            return None
        return ChunkEmbeddingRecord(
            chunk_id=chunk_id,
            embedding_model=embedding_model,
            vector=numeric_vector,
            updated_at=updated_at,
            embedding_space_id=(
                embedding_space_id if isinstance(embedding_space_id, str) else None
            ),
            dimension=(
                int(dimension)
                if isinstance(dimension, int) and dimension > 0
                else len(numeric_vector)
            ),
            content_hash=content_hash if isinstance(content_hash, str) else None,
        )


chunk_embedding_store = ChunkEmbeddingStore()
