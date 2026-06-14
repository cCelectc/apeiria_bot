"""Runtime assembly phase."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

from apeiria.runtime.context import ApeiriaRuntime

if TYPE_CHECKING:
    from pathlib import Path

    from apeiria.access.service import AccessService
    from apeiria.app.ai.application import AIApplication
    from apeiria.app.chat.service import WebChatService
    from apeiria.app.plugins.management import PluginManagementService
    from apeiria.app.system.management import SystemManagementService
    from apeiria.app.system.project_update import ProjectUpdateService
    from apeiria.config.project import ProjectConfigService
    from apeiria.conversation.service import ChatSessionService
    from apeiria.db.runtime import ApeiriaDatabase
    from apeiria.plugins.catalog import PluginGovernanceService


class _EnvironmentService(Protocol):
    @property
    def project_root(self) -> Path: ...


@dataclass(frozen=True, slots=True)
class RuntimeServices:
    project_config: ProjectConfigService = field()  # type: ignore[assignment]
    environment: _EnvironmentService = field()  # type: ignore[assignment]
    database: ApeiriaDatabase = field()  # type: ignore[assignment]
    conversation: ChatSessionService = field()  # type: ignore[assignment]
    chat: WebChatService = field()  # type: ignore[assignment]
    plugin_governance: PluginGovernanceService = field()  # type: ignore[assignment]
    plugin_management: PluginManagementService = field()  # type: ignore[assignment]
    access: AccessService = field()  # type: ignore[assignment]
    system: SystemManagementService = field()  # type: ignore[assignment]
    project_update: ProjectUpdateService = field()  # type: ignore[assignment]
    ai: AIApplication = field()  # type: ignore[assignment]


def _get_runtime_services() -> RuntimeServices:
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

    return RuntimeServices(
        project_config=project_config_service,
        environment=environment_service,
        database=database_runtime,
        conversation=chat_session_service,
        chat=web_chat_service,
        plugin_governance=plugin_governance_service,
        plugin_management=plugin_management_service,
        access=access_service,
        system=system_management_service,
        project_update=project_update_service,
        ai=ai_application,
    )


def build_runtime() -> ApeiriaRuntime:
    svc = _get_runtime_services()

    return ApeiriaRuntime(
        project_root=svc.environment.project_root,
        config=svc.project_config,
        environment=svc.environment,
        database=svc.database,
        conversation=svc.conversation,
        chat=svc.chat,
        plugins=svc.plugin_governance,
        plugin_management=svc.plugin_management,
        access=svc.access,
        system=svc.system,
        project_update=svc.project_update,
        ai=svc.ai,  # type: ignore[arg-type]
    )
