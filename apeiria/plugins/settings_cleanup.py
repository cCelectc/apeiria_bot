"""Plugin project-config cleanup helpers."""

from __future__ import annotations

from dataclasses import dataclass

import nonebot

from apeiria.config.project import project_config_service
from apeiria.plugins.metadata.module_cache import is_module_importable
from apeiria.plugins.settings_support import get_plugin_declared_configs


@dataclass(frozen=True)
class OrphanPluginConfigItem:
    """One orphaned plugin config entry in project config."""

    section: str
    module_name: str | None
    has_section: bool
    reason: str


class PluginConfigCleanupService:
    """Find and remove orphan plugin config sections."""

    async def list_orphan_plugin_configs(self) -> list[OrphanPluginConfigItem]:
        loaded_plugins = list(nonebot.get_loaded_plugins())
        loaded_sections = {
            get_plugin_declared_configs(plugin.module_name).section
            for plugin in loaded_plugins
        }
        loaded_modules = {plugin.module_name for plugin in loaded_plugins}
        section_names = project_config_service.read_project_plugin_section_names()
        module_map = project_config_service.read_project_plugin_module_map()

        orphaned: list[OrphanPluginConfigItem] = []
        seen_sections: set[str] = set()

        for section in section_names:
            mapped_module = module_map.get(section)
            if section in loaded_sections:
                continue
            if mapped_module and (
                mapped_module in loaded_modules or is_module_importable(mapped_module)
            ):
                continue
            orphaned.append(
                OrphanPluginConfigItem(
                    section=section,
                    module_name=mapped_module,
                    has_section=True,
                    reason=(
                        "mapped module is missing"
                        if mapped_module
                        else "no loaded plugin uses this section"
                    ),
                )
            )
            seen_sections.add(section)

        for section, module_name in module_map.items():
            if section in seen_sections or section in loaded_sections:
                continue
            if is_module_importable(module_name):
                continue
            orphaned.append(
                OrphanPluginConfigItem(
                    section=section,
                    module_name=module_name,
                    has_section=section in section_names,
                    reason="mapped module is missing",
                )
            )

        return sorted(orphaned, key=lambda item: item.section)

    async def cleanup_orphan_plugin_configs(self) -> list[OrphanPluginConfigItem]:
        orphaned = await self.list_orphan_plugin_configs()
        if not orphaned:
            return []

        mapping_updates: dict[str, str | None] = {}
        for item in orphaned:
            if item.has_section:
                project_config_service.remove_project_plugin_section(item.section)
            mapping_updates[item.section] = None

        if mapping_updates:
            project_config_service.write_project_plugin_module_map(mapping_updates)
        return orphaned


plugin_config_cleanup_service = PluginConfigCleanupService()
