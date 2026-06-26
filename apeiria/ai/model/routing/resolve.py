from __future__ import annotations

from nonebot.log import logger
from sqlalchemy import select

from apeiria.conversation.service import get_session_by_id
from apeiria.db.engine import get_session
from apeiria.db.models.ai_settings import AIRuntimeSettings
from apeiria.db.models.ai_source import AIChatModel


async def resolve_model(session_id: str) -> AIChatModel | None:
    session = await get_session_by_id(session_id)

    async with get_session() as db:
        settings = (
            await db.execute(select(AIRuntimeSettings).where(AIRuntimeSettings.id == 1))
        ).scalar_one_or_none()

        if session and session.model_override:
            model = (
                await db.execute(
                    select(AIChatModel).where(
                        AIChatModel.model_id == session.model_override,
                        AIChatModel.enabled == 1,
                    )
                )
            ).scalar_one_or_none()
            if model:
                return model
            logger.warning(
                "Session %s model_override '%s' not found or disabled, falling back",
                session_id,
                session.model_override,
            )

        if settings and settings.default_chat_model:
            model = (
                await db.execute(
                    select(AIChatModel).where(
                        AIChatModel.model_id == settings.default_chat_model,
                        AIChatModel.enabled == 1,
                    )
                )
            ).scalar_one_or_none()
            if model:
                return model
            logger.warning(
                "default_chat_model '%s' not found or disabled",
                settings.default_chat_model,
            )

        return None
