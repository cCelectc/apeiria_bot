from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import delete as sqla_delete
from sqlalchemy import func, select

from apeiria.db.engine import get_session
from apeiria.db.models.ai_memory import Fact
from apeiria.webui.auth import require_auth

router = APIRouter()


class MemoryResponse(BaseModel):
    id: int
    user_id: str
    session_id: str
    content: str
    importance: float
    embedding_status: str
    last_reinforced_at: str
    created_at: str


class MemoryListResponse(BaseModel):
    items: list[MemoryResponse]
    total: int


class MemoryBulkDelete(BaseModel):
    ids: list[int]


def _to_response(f: Fact) -> MemoryResponse:
    return MemoryResponse(
        id=f.id,
        user_id=f.user_id,
        session_id=f.session_id,
        content=f.content,
        importance=f.importance,
        embedding_status=f.embedding_status,
        last_reinforced_at=f.last_reinforced_at,
        created_at=f.created_at,
    )


@router.get("", response_model=MemoryListResponse)
async def list_memories(
    _: Annotated[Any, Depends(require_auth)],
    user_id: Annotated[str | None, Query()] = None,
    session_id: Annotated[str | None, Query()] = None,
    search: Annotated[str | None, Query()] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> MemoryListResponse:
    async with get_session() as db:
        q = select(Fact)
        count_q = select(func.count()).select_from(Fact)
        if user_id:
            q = q.where(Fact.user_id == user_id)
            count_q = count_q.where(Fact.user_id == user_id)
        if session_id:
            q = q.where(Fact.session_id == session_id)
            count_q = count_q.where(Fact.session_id == session_id)
        if search:
            q = q.where(Fact.content.contains(search))
            count_q = count_q.where(Fact.content.contains(search))
        q = q.order_by(Fact.created_at.desc()).offset(offset).limit(limit)

        total = (await db.execute(count_q)).scalar() or 0
        result = await db.execute(q)
        items = [_to_response(r) for r in result.scalars()]
        return MemoryListResponse(items=items, total=total)


@router.get("/{memory_id}", response_model=MemoryResponse)
async def get_memory(
    memory_id: int,
    _: Annotated[Any, Depends(require_auth)],
) -> MemoryResponse:
    async with get_session() as db:
        f = await db.get(Fact, memory_id)
        if not f:
            raise HTTPException(404, "Memory not found")
        return _to_response(f)


@router.post("/bulk-delete")
async def bulk_delete_memories(
    body: MemoryBulkDelete,
    _: Annotated[Any, Depends(require_auth)],
) -> dict[str, int]:
    async with get_session() as db:
        await db.execute(sqla_delete(Fact).where(Fact.id.in_(body.ids)))
        await db.commit()
    return {"deleted": len(body.ids)}
