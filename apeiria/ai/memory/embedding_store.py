"""File-backed storage for memory embedding payloads."""

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


_CACHE_MAX_SIZE = 512
_SENTINEL = object()


class AIMemoryEmbeddingStore:
    """Read and write memory embedding payloads outside the database."""

    def __init__(self) -> None:
        self._cache: dict[str, AIMemoryEmbeddingRecord | None] = {}

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
        atomic_write_text(
            _record_path(memory_id),
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
        )
        self._cache[memory_id] = record
        self._evict_if_needed()
        return record

    def get(self, *, memory_id: str) -> AIMemoryEmbeddingRecord | None:
        cached = self._cache.get(memory_id, _SENTINEL)
        if cached is not _SENTINEL:
            return cached  # type: ignore[return-value]
        target = _record_path(memory_id)
        if not target.is_file():
            self._cache[memory_id] = None
            self._evict_if_needed()
            return None
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        record = self._record_from_payload(memory_id=memory_id, payload=payload)
        self._cache[memory_id] = record
        self._evict_if_needed()
        return record

    def get_many(
        self, memory_ids: list[str]
    ) -> dict[str, AIMemoryEmbeddingRecord | None]:
        return {mid: self.get(memory_id=mid) for mid in memory_ids}

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
        self._cache.pop(memory_id, None)
        target = _record_path(memory_id)
        try:
            target.unlink()
        except FileNotFoundError:
            return False
        return True

    def _evict_if_needed(self) -> None:
        if len(self._cache) > _CACHE_MAX_SIZE:
            evict_count = len(self._cache) - _CACHE_MAX_SIZE
            keys = list(self._cache)[:evict_count]
            for key in keys:
                del self._cache[key]


ai_memory_embedding_store = AIMemoryEmbeddingStore()

__all__ = [
    "AIMemoryEmbeddingRecord",
    "AIMemoryEmbeddingStore",
    "ai_memory_embedding_store",
]
