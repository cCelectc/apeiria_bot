"""Non-mutating diagnostics for retired local project compatibility state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True, slots=True)
class RetiredProjectStateIssue:
    """One stale local state shape that needs explicit operator migration."""

    key: str
    message: str
    hint: str


def inspect_retired_project_state(
    _project_root: "Path",
) -> tuple[RetiredProjectStateIssue, ...]:
    """Inspect retired project-local state without mutating files."""
    return ()


__all__ = [
    "RetiredProjectStateIssue",
    "inspect_retired_project_state",
]
