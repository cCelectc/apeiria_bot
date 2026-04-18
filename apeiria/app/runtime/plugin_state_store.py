"""Runtime-facing plugin state store.

Wraps the database-backed plugin state queries so runtime callers see a
stable `PluginRuntimeState` object instead of talking to PluginInfo rows
directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.app.plugins.models import PluginRuntimeState
from apeiria.infra.runtime.plugin_state import get_disabled_plugin_modules

if TYPE_CHECKING:
    from collections.abc import Collection


class PluginRuntimeStateStore:
    """Runtime state reader for plugin modules."""

    async def get_disabled_modules(
        self,
        module_names: "Collection[str] | None" = None,
    ) -> set[str]:
        return await get_disabled_plugin_modules(module_names)

    async def get_state(
        self,
        module_name: str,
        *,
        is_loaded: bool,
    ) -> PluginRuntimeState:
        disabled = await get_disabled_plugin_modules((module_name,))
        return PluginRuntimeState(
            is_loaded=is_loaded and module_name not in disabled,
            is_pending_uninstall=False,
        )

    async def get_states(
        self,
        module_names: "Collection[str]",
        *,
        loaded_modules: "Collection[str]",
    ) -> dict[str, PluginRuntimeState]:
        disabled = await get_disabled_plugin_modules(module_names)
        loaded_set = set(loaded_modules)
        return {
            module: PluginRuntimeState(
                is_loaded=module in loaded_set and module not in disabled,
                is_pending_uninstall=False,
            )
            for module in module_names
        }


plugin_runtime_state_store = PluginRuntimeStateStore()
