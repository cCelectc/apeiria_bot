from __future__ import annotations

from nonebot.log import logger
from sqlalchemy import select

from apeiria.ai.memory.service import search
from apeiria.ai.types import PromptFragment, SessionContext
from apeiria.db.engine import get_session
from apeiria.db.models.ai_settings import AIRuntimeSettings


async def memory_context_handler(
    ctx: SessionContext,
) -> PromptFragment | None:
    if not ctx.user_id:
        return None
    try:
        async with get_session() as db:
            settings = (
                await db.execute(
                    select(AIRuntimeSettings).where(AIRuntimeSettings.id == 1)
                )
            ).scalar_one_or_none()
        if not settings:
            return None

        recent_text = " ".join(m.content for m in ctx.messages[-3:] if m.content)
        if not recent_text:
            return None

        facts = await search(
            ctx.user_id,
            ctx.session_id,
            recent_text,
            settings=settings,
            top_k=5,
        )
        if not facts:
            return None

        lines = [f"- {f.content}" for f in facts]
        content = "以下是你记住的关于该用户的信息：\n" + "\n".join(lines)
        return PromptFragment(role="system", content=content, placement="after")
    except Exception:  # noqa: BLE001
        logger.warning("Memory handler failed", exc_info=True)
        return None
