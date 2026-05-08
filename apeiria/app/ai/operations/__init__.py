"""AI management write application entry."""

from __future__ import annotations

from dataclasses import dataclass

from .errors import (
    AIAdminModelNotFoundError,
    AISourceDeleteBlockedError,
    AISourceModelDeleteBlockedError,
    AISourceModelFetchConfigError,
    AISourceModelFetchUpstreamError,
    AISourceModelTestConfigError,
    AISourceModelTestUpstreamError,
)
from .future_tasks import FutureTasksAdminMixin
from .knowledge import KnowledgeAdminMixin
from .memories import MemoriesAdminMixin
from .models import ModelsAdminMixin
from .person_profiles import PersonProfilesAdminMixin
from .personas import PersonasAdminMixin
from .relationships import RelationshipsAdminMixin
from .sources import SourcesAdminMixin
from .tools import ToolsAdminMixin


@dataclass(frozen=True, slots=True)
class AIOperationsEntry(
    ModelsAdminMixin,
    SourcesAdminMixin,
    PersonasAdminMixin,
    ToolsAdminMixin,
    KnowledgeAdminMixin,
    MemoriesAdminMixin,
    RelationshipsAdminMixin,
    PersonProfilesAdminMixin,
    FutureTasksAdminMixin,
):
    """Application entry for AI management write behavior."""


ai_operations = AIOperationsEntry()

__all__ = [
    "AIAdminModelNotFoundError",
    "AIOperationsEntry",
    "AISourceDeleteBlockedError",
    "AISourceModelDeleteBlockedError",
    "AISourceModelFetchConfigError",
    "AISourceModelFetchUpstreamError",
    "AISourceModelTestConfigError",
    "AISourceModelTestUpstreamError",
    "ai_operations",
]
