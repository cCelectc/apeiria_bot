from __future__ import annotations

"""Runtime context primitives."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

    from apeiria.runtime.control_plane import ApeiriaControlPlane


@dataclass(slots=True)
class ApeiriaRuntime:
    """Minimal runtime kernel composed from owned domain handles."""

    project_root: Path
    config: Any
    environment: Any
    database: Any
    conversation: Any
    chat: Any
    plugins: Any
    access: Any
    ai: Any
    control_plane: ApeiriaControlPlane | None = field(default=None)


_RUNTIME_CONTEXT: dict[str, ApeiriaRuntime | None] = {"current": None}


def set_current_runtime(runtime: ApeiriaRuntime | None) -> None:
    _RUNTIME_CONTEXT["current"] = runtime


def get_current_runtime() -> ApeiriaRuntime | None:
    return _RUNTIME_CONTEXT["current"]
