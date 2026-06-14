"""Unified AI application boundary."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

from .application_entries import LazyApplicationEntry

if TYPE_CHECKING:
    from .diagnostics import AIDiagnosticsEntry
    from .future_tasks import AIFutureTasksEntry
    from .operations import AIOperationsEntry
    from .runtime.factory import LiveRuntimeEntry
    from .sessions import AISessionsEntry
    from .skills import AISkillsEntry


class AILifecycleEntry(Protocol):
    """Startup lifecycle entry exposed by the AI application boundary."""

    async def startup(self) -> object:
        """Prepare startup-owned AI support state."""
        ...

    def inspect(self) -> object:
        """Inspect lifecycle state without mutating it."""
        ...


def _default_lifecycle_entry() -> AILifecycleEntry:
    from .lifecycle import ai_lifecycle_coordinator

    return ai_lifecycle_coordinator


def _default_runtime_entry() -> "LiveRuntimeEntry":
    from .runtime.factory import create_default_ai_runtime_entry

    return create_default_ai_runtime_entry()


def _default_sessions_entry() -> "AISessionsEntry":
    from .sessions import AISessionsEntry

    return AISessionsEntry()


def _default_future_tasks_entry() -> "AIFutureTasksEntry":
    from .future_tasks import AIFutureTasksEntry

    return AIFutureTasksEntry()


def _default_skills_entry() -> "AISkillsEntry":
    from .skills import AISkillsEntry

    return AISkillsEntry()


def _default_operations_entry() -> "AIOperationsEntry":
    from .operations import AIOperationsEntry

    return AIOperationsEntry()


def _default_diagnostics_entry() -> "AIDiagnosticsEntry":
    from .diagnostics import AIDiagnosticsEntry

    return AIDiagnosticsEntry()


@dataclass(frozen=True, slots=True)
class AIApplication:
    """Composition root for AI application entries."""

    _lifecycle: AILifecycleEntry = field(default_factory=_default_lifecycle_entry)
    _runtime: LazyApplicationEntry = field(
        default_factory=lambda: LazyApplicationEntry(_default_runtime_entry)
    )
    _sessions: LazyApplicationEntry = field(
        default_factory=lambda: LazyApplicationEntry(_default_sessions_entry)
    )
    _future_tasks: LazyApplicationEntry = field(
        default_factory=lambda: LazyApplicationEntry(_default_future_tasks_entry)
    )
    _skills: LazyApplicationEntry = field(
        default_factory=lambda: LazyApplicationEntry(_default_skills_entry)
    )
    _operations: LazyApplicationEntry = field(
        default_factory=lambda: LazyApplicationEntry(_default_operations_entry)
    )
    _diagnostics: LazyApplicationEntry = field(
        default_factory=lambda: LazyApplicationEntry(_default_diagnostics_entry)
    )

    @property
    def lifecycle(self) -> AILifecycleEntry:
        return self._lifecycle

    @property
    def runtime(self) -> "LiveRuntimeEntry":
        return self._runtime.resolve()

    @property
    def sessions(self) -> "AISessionsEntry":
        return self._sessions.resolve()

    @property
    def future_tasks(self) -> "AIFutureTasksEntry":
        return self._future_tasks.resolve()

    @property
    def skills(self) -> "AISkillsEntry":
        return self._skills.resolve()

    @property
    def operations(self) -> "AIOperationsEntry":
        return self._operations.resolve()

    @property
    def diagnostics(self) -> "AIDiagnosticsEntry":
        return self._diagnostics.resolve()


ai_application = AIApplication()

__all__ = ["AIApplication", "ai_application"]
