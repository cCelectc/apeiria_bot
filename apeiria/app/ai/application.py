"""Unified AI application boundary."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, cast

from .application_entries import LazyApplicationEntry

if TYPE_CHECKING:
    from .diagnostics import AIDiagnosticsEntry
    from .future_tasks import AIFutureTasksEntry
    from .operations import AIOperationsEntry
    from .runtime.entry import AIRuntimeEntry
    from .sessions import AISessionsEntry


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


def _default_runtime_entry() -> "AIRuntimeEntry":
    from .runtime.factory import create_default_ai_runtime_entry

    return cast("AIRuntimeEntry", create_default_ai_runtime_entry())


def _default_sessions_entry() -> "AISessionsEntry":
    from .sessions import AISessionsEntry

    return AISessionsEntry()


def _default_future_tasks_entry() -> "AIFutureTasksEntry":
    from .future_tasks import AIFutureTasksEntry

    return AIFutureTasksEntry()


def _default_operations_entry() -> "AIOperationsEntry":
    from .operations import AIOperationsEntry

    return AIOperationsEntry()


def _default_diagnostics_entry() -> "AIDiagnosticsEntry":
    from .diagnostics import AIDiagnosticsEntry

    return AIDiagnosticsEntry()


@dataclass(frozen=True, slots=True)
class AIApplication:
    """Composition root for AI application entries."""

    runtime: "AIRuntimeEntry" = field(
        default_factory=lambda: cast(
            "AIRuntimeEntry",
            LazyApplicationEntry(_default_runtime_entry),
        )
    )
    sessions: "AISessionsEntry" = field(
        default_factory=lambda: cast(
            "AISessionsEntry",
            LazyApplicationEntry(_default_sessions_entry),
        )
    )
    future_tasks: "AIFutureTasksEntry" = field(
        default_factory=lambda: cast(
            "AIFutureTasksEntry",
            LazyApplicationEntry(_default_future_tasks_entry),
        )
    )
    operations: "AIOperationsEntry" = field(
        default_factory=lambda: cast(
            "AIOperationsEntry",
            LazyApplicationEntry(_default_operations_entry),
        )
    )
    diagnostics: "AIDiagnosticsEntry" = field(
        default_factory=lambda: cast(
            "AIDiagnosticsEntry",
            LazyApplicationEntry(_default_diagnostics_entry),
        )
    )
    lifecycle: AILifecycleEntry = field(default_factory=_default_lifecycle_entry)


ai_application = AIApplication()

__all__ = ["AIApplication", "ai_application"]
