"""File-backed storage for memory embedding payloads."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from apeiria.db.runtime import database_runtime

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class AIMemoryEmbeddingRecord:
    """Stored embedding payload for one memory item."""

    memory_id: str
    embedding_model: str
    vector: list[float]
    updated_at: str
    embedding_space_id: str | None = None
    dimension: int | None = None
    content_hash: str | None = None


def _storage_dir() -> Path:
    return database_runtime.project_root / "data" / "ai" / "memory_embeddings"


def _record_path(memory_id: str) -> Path:
    safe_memory_id = memory_id.replace("/", "_").replace("\\", "_")
    return _storage_dir() / f"{safe_memory_id}.json"


def _utcnow_text() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class AIMemoryEmbeddingStore:
    """Read and write memory embedding payloads outside the database."""

    def upsert(
        self,
        *,
        memory_id: str,
        embedding_model: str,
        vector: list[float],
        embedding_space_id: str | None = None,
        content_hash: str | None = None,
    ) -> AIMemoryEmbeddingRecord:
        record = AIMemoryEmbeddingRecord(
            memory_id=memory_id,
            embedding_model=embedding_model,
            vector=vector,
            updated_at=_utcnow_text(),
            embedding_space_id=embedding_space_id,
            dimension=len(vector),
            content_hash=content_hash,
        )
        target = _record_path(memory_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp_target = target.with_suffix(".tmp")
        tmp_target.write_text(
            json.dumps(
                {
                    "memory_id": record.memory_id,
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
            encoding="utf-8",
        )
        tmp_target.replace(target)
        return record

    def get(self, *, memory_id: str) -> AIMemoryEmbeddingRecord | None:
        target = _record_path(memory_id)
        if not target.is_file():
            return None
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return self._record_from_payload(memory_id=memory_id, payload=payload)

    def _record_from_payload(
        self,
        *,
        memory_id: str,
        payload: object,
    ) -> AIMemoryEmbeddingRecord | None:
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
        return AIMemoryEmbeddingRecord(
            memory_id=memory_id,
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

    def delete(self, *, memory_id: str) -> bool:
        target = _record_path(memory_id)
        try:
            target.unlink()
        except FileNotFoundError:
            return False
        return True


ai_memory_embedding_store = AIMemoryEmbeddingStore()

__all__ = [
    "AIMemoryEmbeddingRecord",
    "AIMemoryEmbeddingStore",
    "ai_memory_embedding_store",
]
