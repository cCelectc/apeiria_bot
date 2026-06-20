from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from apeiria.db.engine import get_session
from apeiria.db.models.conversation import Message, Session
from apeiria.webui.auth import require_auth

router = APIRouter()


# --- Pydantic models ---


class SessionResponse(BaseModel):
    id: str
    platform: str
    scene_type: str
    scene_id: str
    model_override: str | None
    created_at: str
    last_active_at: str
    last_compacted_message_id: int | None


class MessageResponse(BaseModel):
    id: int
    session_id: str
    role: str
    type: str
    user_id: str | None
    content: str
    message_id: str | None
    meta_json: str | None
    created_at: int


class SessionDetailResponse(BaseModel):
    session: SessionResponse
    messages: list[MessageResponse]


# --- Helpers ---


def _session_to_response(s: Session) -> SessionResponse:
    return SessionResponse(
        id=s.id,
        platform=s.platform,
        scene_type=s.scene_type,
        scene_id=s.scene_id,
        model_override=s.model_override,
        created_at=s.created_at,
        last_active_at=s.last_active_at,
        last_compacted_message_id=s.last_compacted_message_id,
    )


def _message_to_response(m: Message) -> MessageResponse:
    return MessageResponse(
        id=m.id,
        session_id=m.session_id,
        role=m.role,
        type=m.type,
        user_id=m.user_id,
        content=m.content,
        message_id=m.message_id,
        meta_json=m.meta_json,
        created_at=m.created_at,
    )


# --- Endpoints ---


@router.get("", response_model=list[SessionResponse])
async def list_sessions(
    _: Annotated[Any, Depends(require_auth)],
) -> list[SessionResponse]:
    async with get_session() as db:
        result = await db.execute(
            select(Session).order_by(Session.last_active_at.desc()),
        )
        return [_session_to_response(r) for r in result.scalars()]


@router.get("/{session_id}", response_model=SessionDetailResponse)
async def get_session_detail(
    session_id: str,
    _: Annotated[Any, Depends(require_auth)],
) -> SessionDetailResponse:
    async with get_session() as db:
        s = await db.get(Session, session_id)
        if not s:
            raise HTTPException(404, "Session not found")
        result = await db.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at.asc()),
        )
        messages = [_message_to_response(m) for m in result.scalars()]
        return SessionDetailResponse(
            session=_session_to_response(s),
            messages=messages,
        )
