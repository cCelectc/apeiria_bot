from __future__ import annotations

from sqlalchemy import select

from apeiria.ai.relationship.service import get_score, project_emotion
from apeiria.ai.types import PromptFragment, SessionContext
from apeiria.db.engine import get_session
from apeiria.db.models.ai_settings import AIRuntimeSettings


async def relationship_context_handler(
    ctx: SessionContext,
) -> PromptFragment | None:
    if not ctx.user_id:
        return None

    async with get_session() as db:
        settings = (
            await db.execute(select(AIRuntimeSettings).where(AIRuntimeSettings.id == 1))
        ).scalar_one_or_none()

    if settings is None:
        return None

    score = await get_score(ctx.user_id, ctx.session_id, settings=settings)
    emotion_text = project_emotion(score.score)

    return PromptFragment(
        role="system",
        content=(
            f"你与当前用户的关系: {emotion_text}"
            f"（亲密度: {score.score:.0f}/100）。"
            "请根据关系亲密程度调整语气和态度。"
        ),
        placement="first",
    )
