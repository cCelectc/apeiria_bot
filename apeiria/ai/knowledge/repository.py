"""Async SQLAlchemy persistence for default knowledge-base documents and chunks."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import delete, select, update

from apeiria.ai.knowledge.models import (
    KnowledgeChunkDefinition,
    KnowledgeDocumentCreate,
    KnowledgeDocumentDefinition,
)
from apeiria.db.base import _epoch_ms
from apeiria.db.engine import get_session
from apeiria.db.models.ai_knowledge import AIKnowledgeChunk, AIKnowledgeDocument

if TYPE_CHECKING:
    from apeiria.ai.knowledge.models import KnowledgeChunkEmbeddingStatus


class KnowledgeRepository:
    """Own SQL operations for the default knowledge base."""

    async def create_document(
        self,
        create_input: KnowledgeDocumentCreate,
    ) -> KnowledgeDocumentDefinition:
        document_id = f"kdoc_{uuid4().hex}"
        now = _epoch_ms()
        async with get_session() as session:
            doc = AIKnowledgeDocument(
                document_id=document_id,
                title=create_input.title,
                source_file_name=create_input.source_file_name,
                content_hash=create_input.content_hash,
                content_text=create_input.content_text,
                status="pending",
                chunk_count=len(create_input.chunks),
                created_at=now,
                updated_at=now,
            )
            session.add(doc)
            for ordinal, (chunk_hash, text) in enumerate(create_input.chunks):
                chunk = AIKnowledgeChunk(
                    chunk_id=_chunk_id(
                        document_id=document_id,
                        ordinal=ordinal,
                        chunk_hash=chunk_hash,
                    ),
                    document_id=document_id,
                    ordinal=ordinal,
                    chunk_hash=chunk_hash,
                    text=text,
                    char_count=len(text),
                    embedding_status="missing",
                    created_at=now,
                    updated_at=now,
                )
                session.add(chunk)
            await session.commit()
        document = await self.get_document(document_id=document_id)
        assert document is not None
        return document

    async def _replace_document_content(
        self,
        *,
        document_id: str,
        create_input: KnowledgeDocumentCreate,
    ) -> KnowledgeDocumentDefinition | None:
        existing = await self.get_document(document_id=document_id)
        if existing is None:
            return None
        now = _epoch_ms()
        async with get_session() as session:
            await session.execute(
                delete(AIKnowledgeChunk).where(
                    AIKnowledgeChunk.document_id == document_id
                )
            )
            await session.execute(
                update(AIKnowledgeDocument)
                .where(AIKnowledgeDocument.document_id == document_id)
                .values(
                    title=create_input.title,
                    source_file_name=create_input.source_file_name,
                    content_text=create_input.content_text,
                    content_hash=create_input.content_hash,
                    status="pending",
                    chunk_count=len(create_input.chunks),
                    last_error=None,
                    updated_at=now,
                )
            )
            for ordinal, (chunk_hash, text) in enumerate(create_input.chunks):
                chunk = AIKnowledgeChunk(
                    chunk_id=_chunk_id(
                        document_id=document_id,
                        ordinal=ordinal,
                        chunk_hash=chunk_hash,
                    ),
                    document_id=document_id,
                    ordinal=ordinal,
                    chunk_hash=chunk_hash,
                    text=text,
                    char_count=len(text),
                    embedding_status="missing",
                    created_at=now,
                    updated_at=now,
                )
                session.add(chunk)
            await session.commit()
        return await self.get_document(document_id=document_id)

    async def list_documents(self) -> list[KnowledgeDocumentDefinition]:
        async with get_session() as session:
            result = await session.execute(
                select(AIKnowledgeDocument).order_by(
                    AIKnowledgeDocument.updated_at.desc(),
                    AIKnowledgeDocument.document_id.desc(),
                )
            )
            rows = result.scalars().all()
        return [_document_from_orm(row) for row in rows]

    async def get_document(
        self, *, document_id: str
    ) -> KnowledgeDocumentDefinition | None:
        async with get_session() as session:
            result = await session.execute(
                select(AIKnowledgeDocument).where(
                    AIKnowledgeDocument.document_id == document_id
                )
            )
            row = result.scalar_one_or_none()
        if row is None:
            return None
        return _document_from_orm(row)

    async def list_chunks(
        self, *, document_id: str | None = None
    ) -> list[KnowledgeChunkDefinition]:
        stmt = select(AIKnowledgeChunk)
        if document_id is not None:
            stmt = stmt.where(AIKnowledgeChunk.document_id == document_id)
        stmt = stmt.order_by(
            AIKnowledgeChunk.document_id.asc(), AIKnowledgeChunk.ordinal.asc()
        )
        async with get_session() as session:
            result = await session.execute(stmt)
            rows = result.scalars().all()
        return [_chunk_from_orm(row) for row in rows]

    async def mark_chunk_embeddings(
        self,
        *,
        document_id: str,
        chunk_ids: list[str],
        embedding_model: str,
        status: "KnowledgeChunkEmbeddingStatus",
    ) -> None:
        if not chunk_ids:
            return
        now = _epoch_ms()
        async with get_session() as session:
            await session.execute(
                update(AIKnowledgeChunk)
                .where(
                    AIKnowledgeChunk.document_id == document_id,
                    AIKnowledgeChunk.chunk_id.in_(chunk_ids),
                )
                .values(
                    embedding_model=embedding_model,
                    embedding_status=status,
                    updated_at=now,
                )
            )
            await session.commit()

    async def mark_document_status(
        self,
        *,
        document_id: str,
        status: str,
        last_error: str | None = None,
    ) -> None:
        now = _epoch_ms()
        async with get_session() as session:
            await session.execute(
                update(AIKnowledgeDocument)
                .where(AIKnowledgeDocument.document_id == document_id)
                .values(
                    status=status,
                    last_error=last_error,
                    updated_at=now,
                )
            )
            await session.commit()

    async def delete_document(self, *, document_id: str) -> bool:
        async with get_session() as session:
            result = await session.execute(
                delete(AIKnowledgeDocument).where(
                    AIKnowledgeDocument.document_id == document_id
                )
            )
            await session.commit()
        return (result.rowcount or 0) > 0


def _document_from_orm(row: AIKnowledgeDocument) -> KnowledgeDocumentDefinition:
    return KnowledgeDocumentDefinition(
        document_id=row.document_id,
        title=row.title,
        source_file_name=row.source_file_name,
        content_text=row.content_text,
        content_hash=row.content_hash,
        status=row.status,  # type: ignore[arg-type]
        chunk_count=row.chunk_count,
        last_error=row.last_error,
        created_at=_epoch_ms_to_datetime(row.created_at),
        updated_at=_epoch_ms_to_datetime(row.updated_at),
    )


def _chunk_from_orm(row: AIKnowledgeChunk) -> KnowledgeChunkDefinition:
    return KnowledgeChunkDefinition(
        chunk_id=row.chunk_id,
        document_id=row.document_id,
        ordinal=row.ordinal,
        chunk_hash=row.chunk_hash,
        text=row.text,
        char_count=row.char_count,
        embedding_model=row.embedding_model,
        embedding_status=row.embedding_status,  # type: ignore[arg-type]
        created_at=_epoch_ms_to_datetime(row.created_at),
        updated_at=_epoch_ms_to_datetime(row.updated_at),
    )


def _chunk_id(*, document_id: str, ordinal: int, chunk_hash: str) -> str:
    safe_hash = chunk_hash[:12] if chunk_hash else "nohash"
    return f"kchunk_{document_id}_{ordinal}_{safe_hash}"


def _epoch_ms_to_datetime(ms: int | str) -> datetime:
    return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc)
