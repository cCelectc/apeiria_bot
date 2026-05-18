"""Best-effort AI retention cleanup."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from nonebot.log import logger

from apeiria.db.runtime import database_runtime

if TYPE_CHECKING:
    from apeiria.ai.runtime_settings import AIRuntimeSettings


def _iso_cutoff(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=max(days, 1))).isoformat(
        timespec="seconds"
    )


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
        conversation_result = self.cleanup_conversations(
            conversation_retention_days=settings.conversation_retention_days,
            raw_event_retention_days=settings.raw_event_retention_days,
        )
        deleted_tool_execution_count = self.cleanup_tool_executions(
            retention_days=settings.tool_execution_retention_days
        )
        deleted_memory_count = self.cleanup_suppressed_memories(
            retention_days=settings.suppressed_memory_retention_days
        )
        return AIRetentionCleanupResult(
            deleted_messages=conversation_result.deleted_messages,
            deleted_sessions=conversation_result.deleted_sessions,
            cleared_raw_payloads=conversation_result.cleared_raw_payloads,
            deleted_tool_executions=deleted_tool_execution_count,
            deleted_memories=deleted_memory_count,
        )

    def cleanup_conversations(
        self,
        *,
        conversation_retention_days: int,
        raw_event_retention_days: int,
    ) -> AIRetentionCleanupResult:
        """Delete old SQLite-backed conversation rows and raw payloads."""

        with database_runtime.connect_sync() as connection:
            deleted_messages = connection.execute(
                """
                DELETE FROM chat_message
                WHERE created_at < ?
                """,
                (_iso_cutoff(conversation_retention_days),),
            )
            deleted_sessions = connection.execute(
                """
                DELETE FROM chat_session
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM chat_message
                    WHERE chat_message.session_pk = chat_session.id
                )
                """
            )
            cleared_raw_payloads = connection.execute(
                """
                UPDATE chat_message
                SET raw_data_json = NULL
                WHERE raw_data_json IS NOT NULL AND created_at < ?
                """,
                (_iso_cutoff(raw_event_retention_days),),
            )
        return AIRetentionCleanupResult(
            deleted_messages=int(deleted_messages.rowcount or 0),
            deleted_sessions=int(deleted_sessions.rowcount or 0),
            cleared_raw_payloads=int(cleared_raw_payloads.rowcount or 0),
        )

    def cleanup_tool_executions(self, *, retention_days: int) -> int:
        """Delete old SQLite-backed tool execution audit rows."""

        with database_runtime.connect_sync() as connection:
            cursor = connection.execute(
                """
                DELETE FROM ai_tool_execution
                WHERE created_at < ?
                """,
                (_iso_cutoff(retention_days),),
            )
            return int(cursor.rowcount or 0)

    def cleanup_suppressed_memories(self, *, retention_days: int) -> int:
        """Delete old suppressed SQLite-backed memory rows and embeddings."""

        from apeiria.ai.memory.embedding_store import ai_memory_embedding_store

        cutoff = _iso_cutoff(retention_days)
        with database_runtime.connect_sync() as connection:
            rows = connection.execute(
                """
                SELECT memory_id
                FROM ai_memory_item
                WHERE created_at < ? AND lifecycle_state = 'suppressed'
                """,
                (cutoff,),
            ).fetchall()
            memory_ids = [str(row[0]) for row in rows]
            if not memory_ids:
                return 0
            cursor = connection.execute(
                """
                DELETE FROM ai_memory_item
                WHERE created_at < ? AND lifecycle_state = 'suppressed'
                """,
                (cutoff,),
            )
        for memory_id in memory_ids:
            ai_memory_embedding_store.delete(memory_id=memory_id)
        return int(cursor.rowcount or 0)


ai_retention_service = AIRetentionService()
