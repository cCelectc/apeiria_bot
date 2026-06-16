"""Best-effort AI retention cleanup."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from nonebot.log import logger
from sqlalchemy import delete, select, text

from apeiria.db.engine import get_session, rowcount
from apeiria.db.models.ai_memory import AIMemoryItem
from apeiria.db.models.conversation import ChatMessage, ChatSession

if TYPE_CHECKING:
    from apeiria.ai.runtime_settings import AIRuntimeSettings


def _epoch_ms_cutoff(days: int) -> int:
    cutoff_dt = datetime.now(timezone.utc) - timedelta(days=max(days, 1))
    return int(cutoff_dt.timestamp() * 1000)


@dataclass(frozen=True)
class AIRetentionCleanupResult:
    """Counts for one retention cleanup pass."""

    deleted_messages: int = 0
    deleted_sessions: int = 0
    cleared_raw_payloads: int = 0
    deleted_tool_executions: int = 0
    deleted_memories: int = 0

    @property
    def total_changes(self) -> int:
        return (
            self.deleted_messages
            + self.deleted_sessions
            + self.cleared_raw_payloads
            + self.deleted_tool_executions
            + self.deleted_memories
        )


class AIRetentionService:
    """Run conservative AI retention cleanup with in-memory throttling."""

    def __init__(self) -> None:
        self._last_cleanup_at: float = 0.0
        self._cleanup_task: asyncio.Task[None] | None = None

    def maybe_schedule_cleanup(
        self,
        *,
        settings: "AIRuntimeSettings",
    ) -> bool:
        """Schedule cleanup in the background when the interval has elapsed."""

        interval_seconds = max(int(settings.cleanup_interval_minutes), 1) * 60
        now = time.time()
        if self._cleanup_task is not None and not self._cleanup_task.done():
            return False
        if now - self._last_cleanup_at < interval_seconds:
            return False

        self._last_cleanup_at = now
        self._cleanup_task = asyncio.create_task(self._run_cleanup(settings=settings))
        return True

    async def _run_cleanup(
        self,
        *,
        settings: "AIRuntimeSettings",
    ) -> None:
        try:
            result = await self.cleanup(settings=settings)
            if result.total_changes > 0:
                logger.info(
                    "AI retention cleanup changed messages={} sessions={} "
                    "raw_payloads={} tool_executions={} memories={}",
                    result.deleted_messages,
                    result.deleted_sessions,
                    result.cleared_raw_payloads,
                    result.deleted_tool_executions,
                    result.deleted_memories,
                )
        except Exception as exc:  # noqa: BLE001
            logger.opt(exception=exc).warning("AI retention cleanup failed")
        finally:
            self._cleanup_task = None

    async def cleanup(
        self,
        *,
        settings: "AIRuntimeSettings",
    ) -> AIRetentionCleanupResult:
        conversation_result = await self.cleanup_conversations(
            conversation_retention_days=settings.conversation_retention_days,
            raw_event_retention_days=settings.raw_event_retention_days,
        )
        deleted_tool_execution_count = await self.cleanup_tool_executions(
            retention_days=settings.tool_execution_retention_days
        )
        deleted_memory_count = await self.cleanup_suppressed_memories(
            retention_days=settings.suppressed_memory_retention_days
        )
        return AIRetentionCleanupResult(
            deleted_messages=conversation_result.deleted_messages,
            deleted_sessions=conversation_result.deleted_sessions,
            cleared_raw_payloads=conversation_result.cleared_raw_payloads,
            deleted_tool_executions=deleted_tool_execution_count,
            deleted_memories=deleted_memory_count,
        )

    async def cleanup_conversations(
        self,
        *,
        conversation_retention_days: int,
        raw_event_retention_days: int,  # noqa: ARG002
    ) -> AIRetentionCleanupResult:
        """Delete old conversation rows."""

        cutoff = _epoch_ms_cutoff(conversation_retention_days)

        async with get_session() as session:
            msg_result = await session.execute(
                delete(ChatMessage).where(ChatMessage.created_at < cutoff)
            )
            deleted_messages = rowcount(msg_result) or 0

            active_session_ids = (
                select(ChatMessage.session_id).distinct().scalar_subquery()
            )
            sess_result = await session.execute(
                delete(ChatSession).where(
                    ChatSession.session_id.notin_(active_session_ids)
                )
            )
            deleted_sessions = rowcount(sess_result) or 0

            await session.commit()

        return AIRetentionCleanupResult(
            deleted_messages=int(deleted_messages),
            deleted_sessions=int(deleted_sessions),
            cleared_raw_payloads=0,
        )

    async def cleanup_tool_executions(self, *, retention_days: int) -> int:
        """Delete old tool execution audit rows."""

        cutoff = _epoch_ms_cutoff(retention_days)
        async with get_session() as session:
            result = await session.execute(
                text("""
                DELETE FROM ai_tool_execution
                WHERE created_at < :cutoff
                """),
                {"cutoff": cutoff},
            )
            await session.commit()
            return int(rowcount(result) or 0)

    async def cleanup_suppressed_memories(self, *, retention_days: int) -> int:
        """Delete old suppressed memory rows and embeddings."""

        from apeiria.ai.memory.embedding_store import ai_memory_embedding_store

        cutoff = _epoch_ms_cutoff(retention_days)
        async with get_session() as session:
            rows = (
                (
                    await session.execute(
                        select(AIMemoryItem.memory_id).where(
                            AIMemoryItem.created_at < cutoff,
                            AIMemoryItem.lifecycle_state == "suppressed",
                        )
                    )
                )
                .scalars()
                .all()
            )

            if not rows:
                return 0

            memory_ids = [str(mid) for mid in rows]

            result = await session.execute(
                delete(AIMemoryItem).where(
                    AIMemoryItem.created_at < cutoff,
                    AIMemoryItem.lifecycle_state == "suppressed",
                )
            )
            await session.commit()

        for memory_id in memory_ids:
            ai_memory_embedding_store.delete(memory_id=memory_id)

        return int(rowcount(result) or 0)
