"""SQLite persistence for default knowledge-base documents and chunks."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from apeiria.ai.knowledge.models import (
    KnowledgeChunkDefinition,
    KnowledgeDocumentCreate,
    KnowledgeDocumentDefinition,
)
from apeiria.db.runtime import database_runtime

if TYPE_CHECKING:
    import sqlite3

    from apeiria.ai.knowledge.models import KnowledgeChunkEmbeddingStatus


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class KnowledgeRepository:
    """Own SQL operations for the default knowledge base."""

    def create_document(
        self,
        create_input: KnowledgeDocumentCreate,
    ) -> KnowledgeDocumentDefinition:
        document_id = f"kdoc_{uuid4().hex}"
        now = utcnow()
        with database_runtime.transaction_sync() as connection:
            self._insert_document(
                connection,
                document_id=document_id,
                create_input=create_input,
                created_at=now,
                updated_at=now,
            )
            self._insert_chunks(
                connection,
                document_id=document_id,
                chunks=create_input.chunks,
                timestamp=now,
            )
        document = self.get_document(document_id=document_id)
        assert document is not None
        return document

    def replace_document_content(
        self,
        *,
        document_id: str,
        create_input: KnowledgeDocumentCreate,
    ) -> KnowledgeDocumentDefinition | None:
        existing = self.get_document(document_id=document_id)
        if existing is None:
            return None
        now = utcnow()
        with database_runtime.transaction_sync() as connection:
            connection.execute(
                """
                DELETE FROM ai_knowledge_chunk
                WHERE document_id = ?
                """,
                (document_id,),
            )
            connection.execute(
                """
                UPDATE ai_knowledge_document
                SET
                    title = ?,
                    source_file_name = ?,
                    content_text = ?,
                    content_hash = ?,
                    status = 'embedded',
                    chunk_count = ?,
                    last_error = NULL,
                    updated_at = ?
                WHERE document_id = ?
                """,
                (
                    create_input.title,
                    create_input.source_file_name,
                    create_input.content_text,
                    create_input.content_hash,
                    len(create_input.chunks),
                    _datetime_to_text(now),
                    document_id,
                ),
            )
            self._insert_chunks(
                connection,
                document_id=document_id,
                chunks=create_input.chunks,
                timestamp=now,
            )
        return self.get_document(document_id=document_id)

    def list_documents(self) -> list[KnowledgeDocumentDefinition]:
        with database_runtime.connect_sync() as connection:
            rows = connection.execute(
                _SELECT_DOCUMENT_FIELDS
                + """
                ORDER BY updated_at DESC, id DESC
                """
            ).fetchall()
        return [_document_from_row(row) for row in rows]

    def get_document(self, *, document_id: str) -> KnowledgeDocumentDefinition | None:
        with database_runtime.connect_sync() as connection:
            row = connection.execute(
                _SELECT_DOCUMENT_FIELDS
                + """
                WHERE document_id = ?
                """,
                (document_id,),
            ).fetchone()
        if row is None:
            return None
        return _document_from_row(row)

    def list_chunks(
        self, *, document_id: str | None = None
    ) -> list[KnowledgeChunkDefinition]:
        params: tuple[object, ...] = ()
        where = ""
        if document_id is not None:
            where = "WHERE document_id = ?"
            params = (document_id,)
        with database_runtime.connect_sync() as connection:
            rows = connection.execute(
                _SELECT_CHUNK_FIELDS
                + f"""
                {where}
                ORDER BY document_id ASC, ordinal ASC
                """,
                params,
            ).fetchall()
        return [_chunk_from_row(row) for row in rows]

    def mark_chunk_embeddings(
        self,
        *,
        document_id: str,
        chunk_ids: list[str],
        embedding_model: str,
        status: KnowledgeChunkEmbeddingStatus,
    ) -> None:
        if not chunk_ids:
            return
        now_text = _datetime_to_text(utcnow())
        placeholders = ",".join("?" for _ in chunk_ids)
        with database_runtime.connect_sync() as connection:
            connection.execute(
                f"""
                UPDATE ai_knowledge_chunk
                SET
                    embedding_model = ?,
                    embedding_status = ?,
                    updated_at = ?
                WHERE document_id = ?
                    AND chunk_id IN ({placeholders})
                """,
                (embedding_model, status, now_text, document_id, *chunk_ids),
            )

    def mark_document_status(
        self,
        *,
        document_id: str,
        status: str,
        last_error: str | None = None,
    ) -> None:
        with database_runtime.connect_sync() as connection:
            connection.execute(
                """
                UPDATE ai_knowledge_document
                SET
                    status = ?,
                    last_error = ?,
                    updated_at = ?
                WHERE document_id = ?
                """,
                (
                    status,
                    last_error,
                    _datetime_to_text(utcnow()),
                    document_id,
                ),
            )

    def delete_document(self, *, document_id: str) -> bool:
        with database_runtime.connect_sync() as connection:
            cursor = connection.execute(
                """
                DELETE FROM ai_knowledge_document
                WHERE document_id = ?
                """,
                (document_id,),
            )
        return int(cursor.rowcount or 0) > 0

    def _insert_document(
        self,
        connection: "sqlite3.Connection",
        *,
        document_id: str,
        create_input: KnowledgeDocumentCreate,
        created_at: datetime,
        updated_at: datetime,
    ) -> None:
        connection.execute(
            """
            INSERT INTO ai_knowledge_document (
                document_id,
                title,
                source_file_name,
                content_text,
                content_hash,
                status,
                chunk_count,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document_id,
                create_input.title,
                create_input.source_file_name,
                create_input.content_text,
                create_input.content_hash,
                "embedded",
                len(create_input.chunks),
                _datetime_to_text(created_at),
                _datetime_to_text(updated_at),
            ),
        )

    def _insert_chunks(
        self,
        connection: "sqlite3.Connection",
        *,
        document_id: str,
        chunks: tuple[tuple[str, str], ...],
        timestamp: datetime,
    ) -> None:
        timestamp_text = _datetime_to_text(timestamp)
        for ordinal, (chunk_hash, text) in enumerate(chunks):
            connection.execute(
                """
                INSERT INTO ai_knowledge_chunk (
                    chunk_id,
                    document_id,
                    ordinal,
                    chunk_hash,
                    text,
                    char_count,
                    embedding_status,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _chunk_id(
                        document_id=document_id,
                        ordinal=ordinal,
                        chunk_hash=chunk_hash,
                    ),
                    document_id,
                    ordinal,
                    chunk_hash,
                    text,
                    len(text),
                    "missing",
                    timestamp_text,
                    timestamp_text,
                ),
            )


_SELECT_DOCUMENT_FIELDS = """
SELECT
    id,
    document_id,
    title,
    source_file_name,
    content_text,
    content_hash,
    status,
    chunk_count,
    last_error,
    created_at,
    updated_at
FROM ai_knowledge_document
"""

_SELECT_CHUNK_FIELDS = """
SELECT
    id,
    chunk_id,
    document_id,
    ordinal,
    chunk_hash,
    text,
    char_count,
    embedding_model,
    embedding_status,
    created_at,
    updated_at
FROM ai_knowledge_chunk
"""


def _document_from_row(row: tuple[object, ...]) -> KnowledgeDocumentDefinition:
    return KnowledgeDocumentDefinition(
        document_id=str(row[1]),
        title=str(row[2]),
        source_file_name=str(row[3]),
        content_text=str(row[4]),
        content_hash=str(row[5]),
        status=row[6],  # type: ignore[arg-type]
        chunk_count=int(str(row[7])),
        last_error=str(row[8]) if row[8] is not None else None,
        created_at=_text_to_datetime(str(row[9])),
        updated_at=_text_to_datetime(str(row[10])),
    )


def _chunk_from_row(row: tuple[object, ...]) -> KnowledgeChunkDefinition:
    return KnowledgeChunkDefinition(
        chunk_id=str(row[1]),
        document_id=str(row[2]),
        ordinal=int(str(row[3])),
        chunk_hash=str(row[4]),
        text=str(row[5]),
        char_count=int(str(row[6])),
        embedding_model=str(row[7]) if row[7] is not None else None,
        embedding_status=row[8],  # type: ignore[arg-type]
        created_at=_text_to_datetime(str(row[9])),
        updated_at=_text_to_datetime(str(row[10])),
    )


def _datetime_to_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def _chunk_id(*, document_id: str, ordinal: int, chunk_hash: str) -> str:
    safe_hash = chunk_hash[:12] if chunk_hash else "nohash"
    return f"kchunk_{document_id}_{ordinal}_{safe_hash}"


def _text_to_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed
