"""Runtime-state admin entrypoints for sessions, memories, tasks, and relationships."""

from __future__ import annotations

from apeiria.ai.admin.future_tasks import FutureTasksAdminMixin
from apeiria.ai.admin.memories import MemoriesAdminMixin
from apeiria.ai.admin.person_profiles import PersonProfilesAdminMixin
from apeiria.ai.admin.relationships import RelationshipsAdminMixin
from apeiria.ai.admin.sessions import SessionsAdminMixin


class AIRuntimeAdminService(
    FutureTasksAdminMixin,
    MemoriesAdminMixin,
    PersonProfilesAdminMixin,
    RelationshipsAdminMixin,
    SessionsAdminMixin,
):
    """Read and mutation operations for AI runtime-state surfaces."""


ai_runtime_admin_service = AIRuntimeAdminService()

__all__ = ["AIRuntimeAdminService", "ai_runtime_admin_service"]
