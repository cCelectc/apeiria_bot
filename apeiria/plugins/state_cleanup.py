"""Startup cleanup helpers for persisted plugin governance state."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from apeiria._framework_loader import iter_builtin_plugin_modules
from apeiria.config.plugins import plugin_config_service
from apeiria.plugins.repository import plugin_catalog_repository
from apeiria.utils.plugin_introspection import get_module_required_plugins

if TYPE_CHECKING:
    from collections.abc import Collection

logger = logging.getLogger("apeiria.plugins.state_cleanup")


class PluginStateCleanupService:
    """Find and remove orphan persisted plugin governance state."""

    def list_orphan_plugin_modules(
        self,
        *,
        pending_uninstall_modules: "Collection[str]" = (),
    ) -> list[str]:
        persisted_modules = (
            plugin_catalog_repository.get_persisted_plugin_modules_sync()
        )
        if not persisted_modules:
            return []

        builtin_modules = set(iter_builtin_plugin_modules())
        explicit_modules = set(
            plugin_config_service.read_project_plugin_config()["modules"]
        )
        referenced_modules = self._collect_referenced_modules(
            builtin_modules | explicit_modules
        )
        pending_modules = {
            module_name.strip()
            for module_name in pending_uninstall_modules
            if isinstance(module_name, str) and module_name.strip()
        }
        return [
            module_name
            for module_name in sorted(persisted_modules)
            if module_name not in builtin_modules
            and module_name not in referenced_modules
            and module_name not in pending_modules
        ]

    def cleanup_orphan_plugin_state(
        self,
        *,
        pending_uninstall_modules: "Collection[str]" = (),
    ) -> list[str]:
        orphaned_modules = self.list_orphan_plugin_modules(
            pending_uninstall_modules=pending_uninstall_modules,
        )
        removed_modules = plugin_catalog_repository.delete_plugin_records_sync(
            orphaned_modules
        )
        if removed_modules:
            logger.info(
                "Removed %d orphan plugin_state rows during startup: %s",
                len(removed_modules),
                ", ".join(removed_modules),
            )
        return removed_modules

    def _collect_referenced_modules(self, seed_modules: set[str]) -> set[str]:
        referenced = set(seed_modules)
        pending = list(seed_modules)

        while pending:
            module_name = pending.pop()
            dependencies = get_module_required_plugins(module_name)
            for dependency in dependencies:
                if dependency in referenced:
                    continue
                referenced.add(dependency)
                pending.append(dependency)
        return referenced


plugin_state_cleanup_service = PluginStateCleanupService()
