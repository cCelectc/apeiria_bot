"""Application-facing admin facade for AI domain inspection.

This module composes all domain-scoped admin mixins into one `AIAdminService`
singleton (`ai_admin_service`). Each domain lives in its own `*_admin.py`:
sources / models / personas / memories / sessions / future_tasks /
relationships / person_profiles / tools.

Errors are re-exported at module scope so existing HTTP route imports from
`apeiria.ai.admin.service` keep working after the split.
"""

from __future__ import annotations

from apeiria.ai.admin.errors import (
    AIAdminModelNotFoundError,
    AISourceDeleteBlockedError,
    AISourceModelDeleteBlockedError,
    AISourceModelFetchConfigError,
    AISourceModelFetchUpstreamError,
    AISourceModelTestConfigError,
    AISourceModelTestUpstreamError,
)
from apeiria.ai.admin.future_tasks import FutureTasksAdminMixin
from apeiria.ai.admin.memories import MemoriesAdminMixin
from apeiria.ai.admin.models import ModelsAdminMixin
from apeiria.ai.admin.person_profiles import PersonProfilesAdminMixin
from apeiria.ai.admin.personas import PersonasAdminMixin
from apeiria.ai.admin.relationships import RelationshipsAdminMixin
from apeiria.ai.admin.sessions import SessionsAdminMixin
from apeiria.ai.admin.sources import SourcesAdminMixin
from apeiria.ai.admin.tools import ToolsAdminMixin


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
