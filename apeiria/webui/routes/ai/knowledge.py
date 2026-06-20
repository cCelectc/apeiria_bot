from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select

from apeiria.db.engine import get_session
from apeiria.db.models.ai_knowledge import KnowledgeChunk, KnowledgeDocument
from apeiria.webui.auth import require_auth

router = APIRouter()


class DocumentResponse(BaseModel):
    id: int
    title: str
    source_file_name: str
    status: str
    chunk_count: int
    last_error: str | None
    created_at: str
    updated_at: str


class ChunkResponse(BaseModel):
    id: int
    document_id: int
    content: str
    chunk_index: int
    embedding_model: str | None
    embedding_status: str


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int


def _doc_to_response(d: KnowledgeDocument) -> DocumentResponse:
    return DocumentResponse(
        id=d.id,
        title=d.title,
        source_file_name=d.source_file_name,
        status=d.status,
        chunk_count=d.chunk_count,
        last_error=d.last_error,
        created_at=d.created_at,
        updated_at=d.updated_at,
    )


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    _: Annotated[Any, Depends(require_auth)],
    search: Annotated[str | None, Query()] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> DocumentListResponse:
    async with get_session() as db:
        q = select(KnowledgeDocument)
        count_q = select(func.count()).select_from(KnowledgeDocument)
        if search:
            q = q.where(KnowledgeDocument.title.contains(search))
            count_q = count_q.where(
                KnowledgeDocument.title.contains(search),
            )
        q = (
            q.order_by(
                KnowledgeDocument.created_at.desc(),
            )
            .offset(offset)
            .limit(limit)
        )

        total = (await db.execute(count_q)).scalar() or 0
        result = await db.execute(q)
        items = [_doc_to_response(r) for r in result.scalars()]
        return DocumentListResponse(items=items, total=total)


@router.get(
    "/documents/{document_id}",
    response_model=DocumentResponse,
)
async def get_document(
    document_id: int,
    _: Annotated[Any, Depends(require_auth)],
) -> DocumentResponse:
    async with get_session() as db:
        doc = await db.get(KnowledgeDocument, document_id)
        if not doc:
            raise HTTPException(404, "Document not found")
        return _doc_to_response(doc)


@router.get(
    "/documents/{document_id}/chunks",
    response_model=list[ChunkResponse],
)
async def list_chunks(
    document_id: int,
    _: Annotated[Any, Depends(require_auth)],
) -> list[ChunkResponse]:
    async with get_session() as db:
        doc = await db.get(KnowledgeDocument, document_id)
        if not doc:
            raise HTTPException(404, "Document not found")
        result = await db.execute(
            select(KnowledgeChunk)
            .where(KnowledgeChunk.document_id == document_id)
            .order_by(KnowledgeChunk.chunk_index),
        )
        return [
            ChunkResponse(
                id=c.id,
                document_id=c.document_id,
                content=c.content,
                chunk_index=c.chunk_index,
                embedding_model=c.embedding_model,
                embedding_status=c.embedding_status,
            )
            for c in result.scalars()
        ]


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(
    document_id: int,
    _: Annotated[Any, Depends(require_auth)],
) -> None:
    async with get_session() as db:
        doc = await db.get(KnowledgeDocument, document_id)
        if not doc:
            raise HTTPException(404, "Document not found")
        await db.delete(doc)
        await db.commit()
