"""Control-plane admin entrypoints for AI sources, models, personas, and tools."""

from __future__ import annotations

from apeiria.app.ai.admin.errors import (
    AIAdminModelNotFoundError,
    AISourceDeleteBlockedError,
    AISourceModelDeleteBlockedError,
    AISourceModelFetchConfigError,
    AISourceModelFetchUpstreamError,
    AISourceModelTestConfigError,
    AISourceModelTestUpstreamError,
)
from apeiria.app.ai.admin.models import ModelsAdminMixin
from apeiria.app.ai.admin.personas import PersonasAdminMixin
from apeiria.app.ai.admin.sources import SourcesAdminMixin
from apeiria.app.ai.admin.tools import ToolsAdminMixin


class AIControlAdminService(
    ModelsAdminMixin,
    PersonasAdminMixin,
    SourcesAdminMixin,
    ToolsAdminMixin,
):
    """Read and mutation operations for AI control-plane state."""


ai_control_admin_service = AIControlAdminService()

__all__ = [
    "AIAdminModelNotFoundError",
    "AIControlAdminService",
    "AISourceDeleteBlockedError",
    "AISourceModelDeleteBlockedError",
    "AISourceModelFetchConfigError",
    "AISourceModelFetchUpstreamError",
    "AISourceModelTestConfigError",
    "AISourceModelTestUpstreamError",
    "ai_control_admin_service",
]
