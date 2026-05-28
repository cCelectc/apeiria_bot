"""Executable tool and execution admin operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.app.ai.lifecycle import ensure_ai_runtime_support_initialized
from apeiria.app.ai.wiring import ai_wiring

if TYPE_CHECKING:
    from apeiria.ai.tools import (
        AIToolDefinition,
        AIToolExecutionView,
        AIToolPolicy,
    )


class ToolsAdminMixin:
    """Admin read operations for executable tools and executions."""

    @staticmethod
    def _ensure_ai_support_ready() -> None:
        ensure_ai_runtime_support_initialized(source="admin_fallback")

    def list_tools(
        self,
        policy: "AIToolPolicy | None" = None,
    ) -> list["AIToolDefinition"]:
        self._ensure_ai_support_ready()
        return ai_wiring.tool_service.list_tool_specs(policy)

    async def list_tool_executions(
        self,
        *,
        session_id: str,
    ) -> list["AIToolExecutionView"]:
        return await ai_wiring.tool_service.list_executions(session_id=session_id)

    async def list_recent_tool_executions(
        self,
        *,
        limit: int,
    ) -> list["AIToolExecutionView"]:
        return await ai_wiring.tool_service.list_recent_executions(limit=limit)


__all__ = ["ToolsAdminMixin"]
