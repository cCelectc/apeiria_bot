"""Runtime control plane primitives."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from apeiria.app.system.management import (
    DashboardStatusSnapshot,
    system_management_service,
)

if TYPE_CHECKING:
    from apeiria.runtime.context import ApeiriaRuntime


class ApeiriaControlPlane:
    """Read-side runtime control plane."""

    def __init__(self, runtime: ApeiriaRuntime) -> None:
        self._runtime = runtime

    async def list_plugins(self) -> list[Any]:
        return await self._runtime.plugins.list_plugins()

    async def list_plugin_catalog_entries(self) -> list[Any]:
        from apeiria.app.plugins.management import plugin_management_service

        return await plugin_management_service.list_plugins()

    async def get_plugin_workbench(self) -> Any:
        from apeiria.app.plugins.management import plugin_management_service

        return await plugin_management_service.build_plugin_workbench(
            plugins=await self.list_plugin_catalog_entries(),
            can_package_update=self.can_plugin_package_update,
        )

    def can_plugin_package_update(self, plugin: Any) -> bool:
        from apeiria.app.plugins.management import plugin_management_service

        return plugin_management_service.can_package_update(plugin)

    async def list_access_rules(self) -> list[Any]:
        from apeiria.app.access.management import access_management_service

        return await access_management_service.list_access_rules()

    async def get_dashboard_status(self) -> DashboardStatusSnapshot:
        return await system_management_service.get_status_snapshot()

    def get_dashboard_events(self) -> list[Any]:
        return system_management_service.get_recent_events()

    def get_web_ui_build_status(self) -> Any:
        return system_management_service.get_web_ui_build_status()

    async def list_ai_managed_sessions(self, *, limit: int = 50) -> list[Any]:
        from apeiria.app.ai import ai_application

        return await ai_application.sessions.list_managed_sessions(limit=limit)

    async def get_ai_managed_session_detail(
        self,
        *,
        session_id: str,
        message_limit: int = 50,
    ) -> Any:
        from apeiria.app.ai import ai_application

        return await ai_application.sessions.get_managed_session_detail(
            session_id=session_id,
            message_limit=message_limit,
        )
