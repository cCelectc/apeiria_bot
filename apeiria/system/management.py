"""Application-owned dashboard and system management workflows."""

from __future__ import annotations

import asyncio
import os
import sys
import time
from dataclasses import dataclass

import nonebot

from apeiria.utils.project_context import (
    current_project_root,
    runtime_project_root_env_var,
)


@dataclass(frozen=True)
class DashboardStatusSnapshot:
    """Status snapshot used by owner-facing dashboard surfaces."""

    status: str
    uptime: float
    plugins_count: int
    disabled_plugins_count: int
    groups_count: int
    disabled_groups_count: int
    access_rules_count: int
    adapters: list[str]


@dataclass(frozen=True)
class DashboardEventSnapshot:
    """Recent high-signal event shown on owner-facing dashboards."""

    timestamp: str
    level: str
    source: str
    message: str


class SystemManagementService:
    """Compose owner-facing runtime status and system operations."""

    def __init__(self) -> None:
        self._start_time = time.time()
        self._background_tasks: set[asyncio.Task[None]] = set()
        self._restart_task: asyncio.Task[None] | None = None

    async def get_status_snapshot(self) -> DashboardStatusSnapshot:
        """Collect the current dashboard metrics snapshot."""
        from apeiria.access.repository import access_repository
        from apeiria.plugins.repository import plugin_catalog_repository

        adapters = list(nonebot.get_adapters().keys())
        plugins = nonebot.get_loaded_plugins()
        enabled_map = await plugin_catalog_repository.get_enabled_map()
        access_rules = await access_repository.list_access_rules()
        disabled_plugins_count = sum(
            1 for enabled in enabled_map.values() if not enabled
        )
        access_rules_count = len(access_rules)

        # group_state table removed in refactoring — graceful fallback
        try:
            from apeiria.access.groups_repository import group_repository

            groups = await group_repository.list_groups()
        except Exception:  # noqa: BLE001
            groups = []
        groups_count = len(groups)
        disabled_groups_count = sum(1 for group in groups if not group.bot_status)

        return DashboardStatusSnapshot(
            status="running",
            uptime=time.time() - self._start_time,
            plugins_count=len(plugins),
            disabled_plugins_count=disabled_plugins_count,
            groups_count=groups_count,
            disabled_groups_count=disabled_groups_count,
            access_rules_count=access_rules_count,
            adapters=adapters,
        )

    def get_recent_events(
        self,
        *,
        limit: int = 8,
    ) -> list[DashboardEventSnapshot]:
        """Return the most recent warning/error events for dashboards."""
        from apeiria.log import log_buffer

        high_signal_levels = {"WARNING", "ERROR", "CRITICAL"}
        entries = [
            DashboardEventSnapshot(
                timestamp=entry.timestamp,
                level=entry.level,
                source=entry.source,
                message=entry.message,
            )
            for entry in log_buffer.get_recent(100)
            if entry.level in high_signal_levels
        ]
        return entries[-limit:][::-1]

    def schedule_restart(self) -> None:
        if self._restart_task is None or self._restart_task.done():
            self._restart_task = asyncio.create_task(self._restart_process())
            self._background_tasks.add(self._restart_task)
            self._restart_task.add_done_callback(self._background_tasks.discard)

    async def _restart_process(self) -> None:
        await asyncio.sleep(0.5)
        argv = sys.argv[:] if sys.argv else ["bot.py"]
        os.environ[runtime_project_root_env_var()] = str(current_project_root())
        os.execv(sys.executable, [sys.executable, *argv])


system_management_service = SystemManagementService()
