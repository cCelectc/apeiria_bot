"""Runtime assembly phase."""

from pathlib import Path
from typing import Any, Protocol

from apeiria.runtime.context import ApeiriaRuntime


class _EnvironmentService(Protocol):
    @property
    def project_root(self) -> Path: ...


def _get_runtime_services() -> tuple[
    Any,
    _EnvironmentService,
    Any,
    Any,
    Any,
    Any,
    Any,
    Any,
    Any,
    Any,
    Any,
]:
    from apeiria.access.service import access_service
    from apeiria.app.ai import ai_application
    from apeiria.app.chat.service import web_chat_service
    from apeiria.app.plugins.management import plugin_management_service
    from apeiria.app.system.management import system_management_service
    from apeiria.app.system.project_update import project_update_service
    from apeiria.config import project_config_service
    from apeiria.conversation.service import chat_session_service
    from apeiria.db.runtime import database_runtime
    from apeiria.environment import environment_service
    from apeiria.plugins.catalog import plugin_governance_service

    return (
        project_config_service,
        environment_service,
        database_runtime,
        chat_session_service,
        web_chat_service,
        plugin_governance_service,
        plugin_management_service,
        access_service,
        system_management_service,
        project_update_service,
        ai_application,
    )


def build_runtime() -> ApeiriaRuntime:
    (
        project_config_service,
        environment_service,
        database_runtime,
        chat_session_service,
        web_chat_service,
        plugin_governance_service,
        plugin_management_service,
        access_service,
        system_management_service,
        project_update_service,
        ai_application,
    ) = _get_runtime_services()

    return ApeiriaRuntime(
        project_root=environment_service.project_root,
        config=project_config_service,
        environment=environment_service,
        database=database_runtime,
        conversation=chat_session_service,
        chat=web_chat_service,
        plugins=plugin_governance_service,
        plugin_management=plugin_management_service,
        access=access_service,
        system=system_management_service,
        project_update=project_update_service,
        ai=ai_application,
    )
