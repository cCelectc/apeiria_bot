"""Runtime-state admin entrypoints for sessions, memories, tasks, and relationships."""

from __future__ import annotations

from apeiria.app.ai.admin.future_tasks import FutureTasksAdminMixin
from apeiria.app.ai.admin.memories import MemoriesAdminMixin
from apeiria.app.ai.admin.person_profiles import PersonProfilesAdminMixin
from apeiria.app.ai.admin.relationships import RelationshipsAdminMixin


class AIRuntimeAdminService(
    FutureTasksAdminMixin,
    MemoriesAdminMixin,
    PersonProfilesAdminMixin,
    RelationshipsAdminMixin,
):
    """Read and mutation operations for AI runtime-state surfaces."""


ai_runtime_admin_service = AIRuntimeAdminService()

__all__ = ["AIRuntimeAdminService", "ai_runtime_admin_service"]
