from __future__ import annotations

from typing import TYPE_CHECKING, Any

from nonebot.log import logger
from sqlalchemy import select

from apeiria.ai.agent.agent import Agent
from apeiria.ai.model.entry import stream as model_stream

if TYPE_CHECKING:
    from apeiria.ai.agent.events import AgentEvent
from apeiria.ai.model.routing import resolve_model
from apeiria.ai.tools.registry import HandlerRegistry, ToolRegistry
from apeiria.conversation.service import append_message as conv_append
from apeiria.db.engine import get_session
from apeiria.db.models.ai_settings import AIRuntimeSettings


async def build_agent(session_id: str) -> Agent | None:
    model = await resolve_model(session_id)
    if not model:
        logger.warning("No model available for session {}", session_id)
        return None

    async with get_session() as db:
        settings = (
            await db.execute(select(AIRuntimeSettings).where(AIRuntimeSettings.id == 1))
        ).scalar_one_or_none()

    compaction_threshold = settings.compaction_threshold if settings else 0.8
    self_review_enabled = bool(settings.self_review_enabled) if settings else False

    async def stream_fn(**kwargs: Any) -> Any:
        async for event in model_stream(model.model_id, **kwargs):
            yield event

    async def compaction_fn() -> None:
        await _compact_session(session_id)

    tools = ToolRegistry.list_all()
    handlers = HandlerRegistry.list_all()

    agent = Agent(
        session_id=session_id,
        stream_fn=stream_fn,
        tools=tools,
        handlers=handlers,
        context_window=model.context_window,
        compaction_threshold=compaction_threshold,
        self_review_enabled=self_review_enabled,
        compaction_fn=compaction_fn,
    )

    async def _persist_reply(event: AgentEvent) -> None:
        if event.data.get("has_reply") and event.data.get("reply_text"):
            try:
                await conv_append(
                    session_id,
                    "assistant",
                    event.data["reply_text"],
                )
            except Exception:  # noqa: BLE001
                logger.warning("Failed to persist reply", exc_info=True)

    agent.event_bus.subscribe("turn:end", _persist_reply)

    return agent


_MIN_MESSAGES_TO_COMPACT = 20


async def _compact_session(session_id: str) -> None:
    from apeiria.conversation.service import (
        append_message,
        load_recent,
        update_session_compaction,
    )

    messages = await load_recent(session_id, limit=200)
    if len(messages) < _MIN_MESSAGES_TO_COMPACT:
        return

    boundary_idx = len(messages) // 2
    boundary_msg = messages[boundary_idx]

    older = messages[:boundary_idx]
    summary_lines = []
    for m in older:
        prefix = m.user_id or m.role
        summary_lines.append(f"[{prefix}] {m.content[:100]}")
    summary = "以下是之前对话的摘要:\n" + "\n".join(summary_lines[-10:])

    await append_message(
        session_id,
        "system",
        summary,
        msg_type="system",
    )

    await update_session_compaction(session_id, boundary_msg.id)
