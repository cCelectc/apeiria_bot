from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.runtime.bootstrapper import ApeiriaBootstrapper
from apeiria.runtime.entry_guard import ensure_entry_environment_ready
from apeiria.utils.project_context import (
    reset_active_project_root,
    set_active_project_root,
)

if TYPE_CHECKING:
    from pathlib import Path


def run(project_root: Path | None = None) -> None:
    token = set_active_project_root(project_root) if project_root is not None else None
    try:
        ensure_entry_environment_ready(project_root=project_root)
        ApeiriaBootstrapper().run()
    finally:
        if token is not None:
            reset_active_project_root(token)


if __name__ == "__main__":
    run()
