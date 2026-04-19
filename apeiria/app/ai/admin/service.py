"""Application-facing admin facade for AI domain inspection.

This module composes all domain-scoped admin mixins into one `AIAdminService`
singleton (`ai_admin_service`). Each domain lives in its own `*_admin.py`:
sources / models / personas / memories / sessions / future_tasks /
relationships / person_profiles / tools.

Errors are re-exported at module scope so existing HTTP route imports from
`apeiria.app.ai.admin.service` keep working after the split.
"""

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
from apeiria.app.ai.admin.future_tasks_admin import FutureTasksAdminMixin
from apeiria.app.ai.admin.memories_admin import MemoriesAdminMixin
from apeiria.app.ai.admin.models_admin import ModelsAdminMixin
from apeiria.app.ai.admin.person_profiles_admin import PersonProfilesAdminMixin
from apeiria.app.ai.admin.personas_admin import PersonasAdminMixin
from apeiria.app.ai.admin.relationships_admin import RelationshipsAdminMixin
from apeiria.app.ai.admin.sessions_admin import SessionsAdminMixin
from apeiria.app.ai.admin.sources_admin import SourcesAdminMixin
from apeiria.app.ai.admin.tools_admin import ToolsAdminMixin


class AIAdminService(
    FutureTasksAdminMixin,
    MemoriesAdminMixin,
    ModelsAdminMixin,
    PersonasAdminMixin,
    PersonProfilesAdminMixin,
    RelationshipsAdminMixin,
    SessionsAdminMixin,
    SourcesAdminMixin,
    ToolsAdminMixin,
):
    """Read and basic override operations for AI admin routes."""


ai_admin_service = AIAdminService()

__all__ = [
    "AIAdminModelNotFoundError",
    "AIAdminService",
    "AISourceDeleteBlockedError",
    "AISourceModelDeleteBlockedError",
    "AISourceModelFetchConfigError",
    "AISourceModelFetchUpstreamError",
    "AISourceModelTestConfigError",
    "AISourceModelTestUpstreamError",
    "ai_admin_service",
]
