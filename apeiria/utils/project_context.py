"""Project-root context shared by host-side operations."""

from __future__ import annotations

from contextvars import ContextVar, Token
from pathlib import Path

_ACTIVE_PROJECT_ROOT: ContextVar[Path | None] = ContextVar(
    "apeiria_active_project_root",
    default=None,
)


def default_project_root() -> Path:
    """Return Apeiria's built-in project root."""
    return Path(__file__).resolve().parents[2]


def resolve_project_root(cwd: str | Path | None = None) -> Path:
    """Resolve a project root argument into an absolute path."""
    if cwd is None:
        return default_project_root()
    return Path(cwd).expanduser().resolve()


def set_active_project_root(project_root: Path) -> Token[Path | None]:
    """Set the active project root for the current execution context."""
    return _ACTIVE_PROJECT_ROOT.set(project_root.resolve())


def reset_active_project_root(token: Token[Path | None]) -> None:
    """Restore the previous project root context."""
    _ACTIVE_PROJECT_ROOT.reset(token)


def active_project_root() -> Path | None:
    """Return the explicitly active project root when one is set."""
    return _ACTIVE_PROJECT_ROOT.get()


def current_project_root() -> Path:
    """Return the active project root or the built-in default."""
    return active_project_root() or default_project_root()
