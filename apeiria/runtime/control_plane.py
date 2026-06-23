"""Runtime control plane primitives."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from apeiria.runtime.context import ApeiriaRuntime
    from apeiria.system.management import (
        DashboardStatusSnapshot,
    )
    from apeiria.system.project_update import (
        ProjectUpdatePlan,
        ProjectUpdatePlanRequest,
        ProjectUpdateStatus,
        ProjectUpdateTask,
    )


class ApeiriaControlPlane:
    """Read-side runtime control plane."""

    def __init__(self, runtime: ApeiriaRuntime) -> None:
        self._runtime = runtime

    async def list_plugins(self) -> list[Any]:
        return await self._runtime.plugins.list_plugins()

    async def list_plugin_catalog_entries(self) -> list[Any]:
        return await self._runtime.plugin_management.list_plugins()

    async def get_plugin_workbench(self) -> Any:
        return await self._runtime.plugin_management.build_plugin_workbench(
            plugins=await self.list_plugin_catalog_entries(),
            can_package_update=self.can_plugin_package_update,
        )

    def can_plugin_package_update(self, plugin: Any) -> bool:
        return self._runtime.plugin_management.can_package_update(plugin)

    async def list_access_rules(self) -> list[Any]:
        return await self._runtime.access.list_access_rules()

    async def get_dashboard_status(self) -> "DashboardStatusSnapshot":
        return await self._runtime.system.get_status_snapshot()

    def get_dashboard_events(self) -> list[Any]:
        return self._runtime.system.get_recent_events()

    def schedule_restart(self) -> None:
        self._runtime.system.schedule_restart()

    def get_project_update_status(self) -> "ProjectUpdateStatus":
        return self._runtime.project_update.inspect()

    def refresh_project_update_status(
        self,
        *,
        force: bool = False,
    ) -> "ProjectUpdateStatus":
        return self._runtime.project_update.refresh_remote_refs(force=force)

    def create_project_update_plan(
        self,
        request: "ProjectUpdatePlanRequest",
    ) -> "ProjectUpdatePlan":
        return self._runtime.project_update.create_plan(request)

    async def create_project_update_task(
        self,
        request: "ProjectUpdatePlanRequest",
    ) -> "ProjectUpdateTask":
        return await self._runtime.project_update.create_task(request)

    def get_project_update_task(self, task_id: str) -> "ProjectUpdateTask | None":
        return self._runtime.project_update.get_task(task_id)

    async def list_ai_managed_sessions(self, *, limit: int = 50) -> list[Any]:
        if self._runtime.ai is None:
            return []
        return await self._runtime.ai.sessions.list_managed_sessions(limit=limit)

    async def get_ai_managed_session_detail(
        self,
        *,
        session_id: str,
        message_limit: int = 50,
    ) -> Any:
        if self._runtime.ai is None:
            return None
        return await self._runtime.ai.sessions.get_managed_session_detail(
            session_id=session_id,
            message_limit=message_limit,
        )
