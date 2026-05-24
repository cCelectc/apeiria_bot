"""Project-root context shared by host-side operations."""

from __future__ import annotations

import os
from contextvars import ContextVar, Token
from pathlib import Path

_ACTIVE_PROJECT_ROOT: ContextVar[Path | None] = ContextVar(
    "apeiria_active_project_root",
    default=None,
)
_RUNTIME_PROJECT_ROOT_ENV_VAR = "APEIRIA_PROJECT_ROOT"


def package_root() -> Path:
    """Return Apeiria's installed package root."""
    return Path(__file__).resolve().parents[2]


def default_project_root() -> Path:
    """Compatibility alias for Apeiria's installed package root."""
    return package_root()


def resolve_project_root(cwd: str | Path | None = None) -> Path:
    """Resolve a project root argument into an absolute path."""
    if cwd is None:
        return Path.cwd().resolve()
    return Path(cwd).expanduser().resolve()


def runtime_project_root_env_var() -> str:
    """Return the environment variable used for cross-process project roots."""
    return _RUNTIME_PROJECT_ROOT_ENV_VAR


def runtime_project_root_from_env() -> Path | None:
    """Return the cross-process runtime project root when one is configured."""
    raw = os.environ.get(_RUNTIME_PROJECT_ROOT_ENV_VAR, "").strip()
    if not raw:
        return None
    return Path(raw).expanduser().resolve()


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
    """Return the active project root, runtime override, or working directory."""
    return (
        active_project_root() or runtime_project_root_from_env() or Path.cwd().resolve()
    )


__all__ = [
    "active_project_root",
    "current_project_root",
    "default_project_root",
    "package_root",
    "reset_active_project_root",
    "resolve_project_root",
    "runtime_project_root_env_var",
    "runtime_project_root_from_env",
    "set_active_project_root",
]
