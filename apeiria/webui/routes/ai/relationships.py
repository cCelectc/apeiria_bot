from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select

from apeiria.db.engine import get_session
from apeiria.db.models.ai_relationship import RelationshipScore
from apeiria.webui.auth import require_auth

router = APIRouter()


class RelationshipResponse(BaseModel):
    user_id: str
    session_id: str
    score: float
    last_updated_at: str


class RelationshipListResponse(BaseModel):
    items: list[RelationshipResponse]
    total: int


@router.get("", response_model=RelationshipListResponse)
async def list_relationships(
    _: Annotated[Any, Depends(require_auth)],
    user_id: Annotated[str | None, Query()] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> RelationshipListResponse:
    async with get_session() as db:
        q = select(RelationshipScore)
        count_q = select(func.count()).select_from(RelationshipScore)
        if user_id:
            q = q.where(RelationshipScore.user_id == user_id)
            count_q = count_q.where(RelationshipScore.user_id == user_id)
        q = q.order_by(RelationshipScore.score.desc()).offset(offset)
        q = q.limit(limit)

        total = (await db.execute(count_q)).scalar() or 0
        result = await db.execute(q)
        items = [
            RelationshipResponse(
                user_id=r.user_id,
                session_id=r.session_id,
                score=r.score,
                last_updated_at=r.last_updated_at,
            )
            for r in result.scalars()
        ]
        return RelationshipListResponse(items=items, total=total)


@router.get("/{user_id}/{session_id}", response_model=RelationshipResponse)
async def get_relationship(
    user_id: str,
    session_id: str,
    _: Annotated[Any, Depends(require_auth)],
) -> RelationshipResponse:
    async with get_session() as db:
        r = await db.get(RelationshipScore, (user_id, session_id))
        if not r:
            raise HTTPException(404, "Relationship not found")


class RelationshipUpdate(BaseModel):
    score: float


@router.patch("/{user_id}/{session_id}", response_model=RelationshipResponse)
async def update_relationship(
    user_id: str,
    session_id: str,
    body: RelationshipUpdate,
    _: Annotated[Any, Depends(require_auth)],
) -> RelationshipResponse:
    async with get_session() as db:
        r = await db.get(RelationshipScore, (user_id, session_id))
        if not r:
            raise HTTPException(404, "Relationship not found")
        r.score = body.score
        await db.commit()
        await db.refresh(r)
        return RelationshipResponse(
            user_id=r.user_id,
            session_id=r.session_id,
            score=r.score,
            last_updated_at=r.last_updated_at,
        )
