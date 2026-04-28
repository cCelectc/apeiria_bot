"""Click context helpers for project-root-aware CLI commands."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import click

from apeiria.environment import EnvironmentService, HealthService
from apeiria.utils.project_context import (
    current_project_root,
    reset_active_project_root,
    resolve_project_root,
    set_active_project_root,
)

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class CLIContext:
    """Per-invocation Apeiria CLI context."""

    project_root: Path


def initialize_cli_context(
    click_context: click.Context,
    *,
    cwd: str | Path | None,
) -> CLIContext:
    """Resolve and attach the active project context to a Click invocation."""
    project_root = resolve_project_root(cwd)
    token = set_active_project_root(project_root)
    click_context.call_on_close(lambda: reset_active_project_root(token))
    context = CLIContext(project_root=project_root)
    click_context.obj = context
    return context


def get_cli_context() -> CLIContext:
    """Return the current Click CLI context, falling back to defaults."""
    click_context = click.get_current_context(silent=True)
    if click_context is not None and isinstance(click_context.obj, CLIContext):
        return click_context.obj
    return CLIContext(project_root=current_project_root())


def active_environment_service() -> EnvironmentService:
    """Build an environment service for the active CLI project root."""
    return EnvironmentService(project_root=get_cli_context().project_root)


def active_health_service() -> HealthService:
    """Build a health service for the active CLI project root."""
    return HealthService(active_environment_service())
