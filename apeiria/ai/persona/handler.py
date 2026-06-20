from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from apeiria.ai.persona.resolver import FALLBACK_PERSONA_PROMPT, resolve
from apeiria.ai.types import PromptFragment, SessionContext
from apeiria.db.engine import get_session
from apeiria.db.models.ai_relationship import AIProfile


async def persona_context_handler(
    ctx: SessionContext,
) -> PromptFragment | None:
    try:
        persona = await resolve(ctx.session_id)
        prompt = persona.prompt if persona else FALLBACK_PERSONA_PROMPT
    except SQLAlchemyError:
        prompt = FALLBACK_PERSONA_PROMPT

    display_suffix = ""
    if ctx.user_id:
        async with get_session() as session:
            profile = (
                await session.execute(
                    select(AIProfile).where(
                        AIProfile.platform == ctx.platform,
                        AIProfile.user_id == ctx.user_id,
                    )
                )
            ).scalar_one_or_none()
            if profile and profile.display_name:
                display_suffix = f"\n你正在和{profile.display_name}聊天。"

    return PromptFragment(
        role="system",
        content=prompt + display_suffix,
        placement="first",
    )
