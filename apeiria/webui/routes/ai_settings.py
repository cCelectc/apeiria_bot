from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from apeiria.db.engine import get_session
from apeiria.db.models.ai_settings import AIRuntimeSettings
from apeiria.webui.auth import require_auth

router = APIRouter()


class AISettingsResponse(BaseModel):
    talk_value: float
    cooldown_seconds: int
    max_replies_per_window: int
    reply_window_seconds: int
    no_action_backoff_base_seconds: int
    no_action_backoff_max_seconds: int
    compaction_threshold: float
    memory_isolate_by_session: int
    memory_half_life_days: float
    memory_floor_ratio: float
    relationship_isolate_by_session: int
    relationship_half_life_days: float
    rerank_enabled: int
    segment_reply_enabled: int
    segment_delay_seconds: float
    self_review_enabled: int
    default_chat_model: str | None
    reasoning_effort: str
    acp_access_mode: str
    searxng_url: str | None


class AISettingsUpdate(BaseModel):
    talk_value: float | None = None
    cooldown_seconds: int | None = None
    max_replies_per_window: int | None = None
    reply_window_seconds: int | None = None
    no_action_backoff_base_seconds: int | None = None
    no_action_backoff_max_seconds: int | None = None
    compaction_threshold: float | None = None
    memory_isolate_by_session: int | None = None
    memory_half_life_days: float | None = None
    memory_floor_ratio: float | None = None
    relationship_isolate_by_session: int | None = None
    relationship_half_life_days: float | None = None
    rerank_enabled: int | None = None
    segment_reply_enabled: int | None = None
    segment_delay_seconds: float | None = None
    self_review_enabled: int | None = None
    default_chat_model: str | None = None
    reasoning_effort: str | None = None
    acp_access_mode: str | None = None
    searxng_url: str | None = None


def _to_response(
    s: AIRuntimeSettings,
) -> AISettingsResponse:
    return AISettingsResponse(
        talk_value=s.talk_value,
        cooldown_seconds=s.cooldown_seconds,
        max_replies_per_window=s.max_replies_per_window,
        reply_window_seconds=s.reply_window_seconds,
        no_action_backoff_base_seconds=s.no_action_backoff_base_seconds,
        no_action_backoff_max_seconds=s.no_action_backoff_max_seconds,
        compaction_threshold=s.compaction_threshold,
        memory_isolate_by_session=s.memory_isolate_by_session,
        memory_half_life_days=s.memory_half_life_days,
        memory_floor_ratio=s.memory_floor_ratio,
        relationship_isolate_by_session=s.relationship_isolate_by_session,
        relationship_half_life_days=s.relationship_half_life_days,
        rerank_enabled=s.rerank_enabled,
        segment_reply_enabled=s.segment_reply_enabled,
        segment_delay_seconds=s.segment_delay_seconds,
        self_review_enabled=s.self_review_enabled,
        default_chat_model=s.default_chat_model,
        reasoning_effort=s.reasoning_effort,
        acp_access_mode=s.acp_access_mode,
        searxng_url=s.searxng_url,
    )


@router.get("")
async def get_settings(
    _: Annotated[Any, Depends(require_auth)],
) -> AISettingsResponse:
    async with get_session() as db:
        settings = (
            await db.execute(select(AIRuntimeSettings).where(AIRuntimeSettings.id == 1))
        ).scalar_one_or_none()
    if not settings:
        raise HTTPException(
            status_code=404,
            detail="Settings not initialized",
        )
    return _to_response(settings)


@router.patch("")
async def update_settings(
    body: AISettingsUpdate,
    _: Annotated[Any, Depends(require_auth)],
) -> AISettingsResponse:
    async with get_session() as db:
        settings = (
            await db.execute(select(AIRuntimeSettings).where(AIRuntimeSettings.id == 1))
        ).scalar_one_or_none()
        if not settings:
            raise HTTPException(
                status_code=404,
                detail="Settings not initialized",
            )
        update_data = body.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(settings, key, value)
        await db.commit()
        await db.refresh(settings)
    return _to_response(settings)
