"""Runtime assembly phase."""

from pathlib import Path
from typing import Any, Protocol

from apeiria.runtime.context import ApeiriaRuntime


class _EnvironmentService(Protocol):
    @property
    def project_root(self) -> Path: ...


def _get_runtime_services() -> tuple[Any, _EnvironmentService, Any, Any, Any, Any]:
    from apeiria.access.service import access_service
    from apeiria.ai.pipeline.service import ai_runtime_service
    from apeiria.config import project_config_service
    from apeiria.db.runtime import database_runtime
    from apeiria.environment import environment_service
    from apeiria.plugins import plugin_governance_service

    return (
        project_config_service,
        environment_service,
        database_runtime,
        plugin_governance_service,
        access_service,
        ai_runtime_service,
    )


def build_runtime() -> ApeiriaRuntime:
    (
        project_config_service,
        environment_service,
        database_runtime,
        plugin_governance_service,
        access_service,
        ai_runtime_service,
    ) = _get_runtime_services()

    return ApeiriaRuntime(
        project_root=environment_service.project_root,
        config=project_config_service,
        environment=environment_service,
        database=database_runtime,
        plugins=plugin_governance_service,
        access=access_service,
        ai=ai_runtime_service,
    )
