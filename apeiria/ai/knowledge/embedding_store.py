"""File-backed storage for default knowledge chunk embeddings."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from apeiria.db.runtime import database_runtime

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class ChunkEmbeddingRecord:
    """Stored embedding payload for one knowledge chunk."""

    chunk_id: str
    embedding_model: str
    vector: list[float]
    updated_at: str


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
    ) -> ChunkEmbeddingRecord:
        record = ChunkEmbeddingRecord(
            chunk_id=chunk_id,
            embedding_model=embedding_model,
            vector=vector,
            updated_at=_utcnow_text(),
        )
        target = _record_path(chunk_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp_target = target.with_suffix(".tmp")
        tmp_target.write_text(
            json.dumps(
                {
                    "chunk_id": record.chunk_id,
                    "embedding_model": record.embedding_model,
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
        )


chunk_embedding_store = ChunkEmbeddingStore()
