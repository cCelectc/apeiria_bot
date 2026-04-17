"""Best-effort AI retention cleanup."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from nonebot.log import logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from apeiria.app.ai.config import AIPluginConfig


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _result_rowcount(result: object) -> int:
    value = getattr(result, "rowcount", 0)
    return int(value or 0)


@dataclass(frozen=True)
class AIRetentionCleanupResult:
    """Counts for one retention cleanup pass."""

    deleted_messages: int = 0
    deleted_sessions: int = 0
    cleared_raw_payloads: int = 0
    deleted_tool_executions: int = 0
    deleted_future_tasks: int = 0
    deleted_memories: int = 0

    @property
    def total_changes(self) -> int:
        return (
            self.deleted_messages
            + self.deleted_sessions
            + self.cleared_raw_payloads
            + self.deleted_tool_executions
            + self.deleted_future_tasks
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
        config: "AIPluginConfig",
    ) -> bool:
        """Schedule cleanup in the background when the interval has elapsed."""

        interval_seconds = max(int(config.cleanup_interval_minutes), 1) * 60
        now = time.time()
        if self._cleanup_task is not None and not self._cleanup_task.done():
            return False
        if now - self._last_cleanup_at < interval_seconds:
            return False

        self._last_cleanup_at = now
        self._cleanup_task = asyncio.create_task(self._run_cleanup(config=config))
        return True

    async def _run_cleanup(
        self,
        *,
        config: "AIPluginConfig",
    ) -> None:
        from nonebot_plugin_orm import get_session

        try:
            async with get_session() as session:
                result = await self.cleanup(session, config=config)
                if result.total_changes > 0:
                    await session.commit()
                    logger.info(
                        "AI retention cleanup changed messages={} sessions={} "
                        "raw_payloads={} tool_executions={} future_tasks={} "
                        "memories={}",
                        result.deleted_messages,
                        result.deleted_sessions,
                        result.cleared_raw_payloads,
                        result.deleted_tool_executions,
                        result.deleted_future_tasks,
                        result.deleted_memories,
                    )
        except Exception as exc:  # noqa: BLE001
            logger.opt(exception=exc).warning("AI retention cleanup failed")
        finally:
            self._cleanup_task = None

    async def cleanup(
        self,
        session: "AsyncSession",
        *,
        config: "AIPluginConfig",
    ) -> AIRetentionCleanupResult:
        from sqlalchemy import delete, exists, select, update

        from apeiria.infra.db.models import (
            AIFutureTask,
            AIMemoryItem,
            AIToolExecution,
            ChatMessage,
            ChatSession,
        )

        now = _utcnow_naive()
        message_cutoff = now - timedelta(
            days=max(config.conversation_retention_days, 1)
        )
        raw_cutoff = now - timedelta(days=max(config.raw_event_retention_days, 1))
        tool_cutoff = now - timedelta(days=max(config.tool_execution_retention_days, 1))
        future_task_cutoff = now - timedelta(
            days=max(config.future_task_retention_days, 1)
        )
        ignored_memory_cutoff = now - timedelta(
            days=max(config.ignored_memory_retention_days, 1)
        )

        deleted_messages = await session.execute(
            delete(ChatMessage).where(ChatMessage.created_at < message_cutoff)
        )
        deleted_sessions = await session.execute(
            delete(ChatSession).where(
                ~exists(
                    select(ChatMessage.id).where(
                        ChatMessage.session_pk == ChatSession.id
                    )
                )
            )
        )
        cleared_raw_payloads = await session.execute(
            update(ChatMessage)
            .where(
                ChatMessage.raw_data_json.is_not(None),
                ChatMessage.created_at < raw_cutoff,
            )
            .values(raw_data_json=None)
        )
        deleted_tool_executions = await session.execute(
            delete(AIToolExecution).where(AIToolExecution.created_at < tool_cutoff)
        )
        deleted_future_tasks = await session.execute(
            delete(AIFutureTask).where(
                AIFutureTask.updated_at < future_task_cutoff,
                AIFutureTask.status.in_(("sent", "cancelled", "failed")),
            )
        )
        deleted_memories = await session.execute(
            delete(AIMemoryItem).where(
                AIMemoryItem.created_at < ignored_memory_cutoff,
                AIMemoryItem.is_ignored.is_(True),
            )
        )

        await session.flush()
        return AIRetentionCleanupResult(
            deleted_messages=_result_rowcount(deleted_messages),
            deleted_sessions=_result_rowcount(deleted_sessions),
            cleared_raw_payloads=_result_rowcount(cleared_raw_payloads),
            deleted_tool_executions=_result_rowcount(deleted_tool_executions),
            deleted_future_tasks=_result_rowcount(deleted_future_tasks),
            deleted_memories=_result_rowcount(deleted_memories),
        )


ai_retention_service = AIRetentionService()
