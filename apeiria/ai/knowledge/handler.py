from __future__ import annotations

from nonebot.log import logger

from apeiria.ai.types import PromptFragment, SessionContext


async def knowledge_context_handler(
    ctx: SessionContext,
) -> PromptFragment | None:
    try:
        from sqlalchemy import select

        from apeiria.ai.knowledge.service import retrieve
        from apeiria.db.engine import get_session
        from apeiria.db.models.ai_settings import AIRuntimeSettings

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

        rerank_id: str | None = None
        results = await retrieve(
            recent_text,
            top_k=3,
            rerank_model_id=(rerank_id if settings.rerank_enabled else None),
        )
        if not results:
            return None

        lines = [f"[知识库] {chunk.content[:500]}" for chunk, _ in results]
        content = "以下是可能相关的知识内容：\n" + "\n---\n".join(lines)
        return PromptFragment(
            role="system",
            content=content,
            placement="after",
        )
    except Exception:  # noqa: BLE001
        logger.warning("Knowledge handler failed", exc_info=True)
        return None
