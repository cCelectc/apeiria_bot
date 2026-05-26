"""Database startup phase."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.db.runtime import ApeiriaDatabase, database_runtime
from apeiria.plugins.state_cleanup import plugin_state_cleanup_service

if TYPE_CHECKING:
    from collections.abc import Collection


def run_database_phase(
    *,
    pending_plugin_module_uninstalls: "Collection[str]" = (),
) -> ApeiriaDatabase:
    """Initialize the runtime database and clean stale plugin governance state."""

    database_runtime.ensure_ready()
    plugin_state_cleanup_service.cleanup_orphan_plugin_state(
        pending_uninstall_modules=pending_plugin_module_uninstalls,
    )
    return database_runtime
