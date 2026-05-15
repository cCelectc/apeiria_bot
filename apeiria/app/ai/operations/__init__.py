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
from .knowledge import KnowledgeAdminMixin
from .memories import MemoriesAdminMixin
from .models import ModelsAdminMixin
from .personas import PersonasAdminMixin
from .profiles import ProfilesAdminMixin
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
    ProfilesAdminMixin,
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
