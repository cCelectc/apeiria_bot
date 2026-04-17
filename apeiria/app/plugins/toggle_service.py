"""Plugin enable/disable preview and apply helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeiria.shared.exceptions import ProtectedPluginError, ResourceNotFoundError
from apeiria.shared.i18n import t

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from apeiria.app.plugins import PluginCatalogEntry


@dataclass(frozen=True)
class PluginTogglePreview:
    """Preview result for enabling or disabling one plugin."""

    module_name: str
    enabled: bool
    allowed: bool
    summary: str
    blocked_reason: str | None
    requires_enable: list[str]
    requires_disable: list[str]
    protected_dependents: list[str]
    missing_dependencies: list[str]


@dataclass(frozen=True)
class PluginToggleResult:
    """Applied toggle result for one plugin operation."""

    module_name: str
    enabled: bool
    affected_modules: list[str]


class PluginToggleService:
    """Own plugin enable/disable preview and apply logic."""

    async def apply_plugin_toggle(
        self,
        module_name: str,
        *,
        enabled: bool,
        cascade: bool,
        list_plugins: Callable[[], Awaitable[list["PluginCatalogEntry"]]],
        set_plugin_enabled_record: Callable[..., Awaitable[bool]],
    ) -> PluginToggleResult:
        preview = await self.preview_toggle_plugin(
            module_name,
            enabled=enabled,
            list_plugins=list_plugins,
        )
        if not preview.allowed:
            raise ProtectedPluginError(
                preview.blocked_reason
                or t("common.required_by_plugins", plugins=module_name)
            )

        related_modules = (
            preview.requires_enable if enabled else preview.requires_disable
        )
        if related_modules and not cascade:
            raise ValueError(preview.summary)

        operation_order = (
            [*preview.requires_enable, module_name]
            if enabled
            else [*preview.requires_disable, module_name]
        )
        changed_modules: list[str] = []
        for target_module in operation_order:
            changed = await set_plugin_enabled_record(
                target_module,
                enabled=enabled,
            )
            if changed:
                changed_modules.append(target_module)

        return PluginToggleResult(
            module_name=module_name,
            enabled=enabled,
            affected_modules=changed_modules,
        )

    async def preview_toggle_plugin(
        self,
        module_name: str,
        *,
        enabled: bool,
        list_plugins: Callable[[], Awaitable[list["PluginCatalogEntry"]]],
    ) -> PluginTogglePreview:
        items = await list_plugins()
        item_map = {item.descriptor.module_name: item for item in items}
        item = item_map.get(module_name)
        if item is None:
            raise ResourceNotFoundError(module_name)

        if enabled:
            return self._preview_enable(item, item_map)
        return self._preview_disable(item, items)

    def _preview_enable(
        self,
        item: "PluginCatalogEntry",
        item_map: dict[str, "PluginCatalogEntry"],
    ) -> PluginTogglePreview:
        requires_enable: list[str] = []
        missing_dependencies: list[str] = []
        for dependency in item.governance_state.required_plugins:
            dependency_item = item_map.get(dependency)
            if dependency_item is None:
                missing_dependencies.append(dependency)
                continue
            if not dependency_item.governance_state.is_global_enabled:
                requires_enable.append(dependency)

        blocked_reason = (
            t(
                "common.missing_required_plugins",
                plugins=", ".join(missing_dependencies),
            )
            if missing_dependencies
            else None
        )
        summary = (
            t("plugins.enabledAction")
            if not requires_enable
            else t(
                "common.enable_required_plugins",
                plugins=", ".join(requires_enable),
            )
        )
        return PluginTogglePreview(
            module_name=item.descriptor.module_name,
            enabled=True,
            allowed=not missing_dependencies,
            summary=summary,
            blocked_reason=blocked_reason,
            requires_enable=requires_enable,
            requires_disable=[],
            protected_dependents=[],
            missing_dependencies=missing_dependencies,
        )

    def _preview_disable(
        self,
        item: "PluginCatalogEntry",
        items: list["PluginCatalogEntry"],
    ) -> PluginTogglePreview:
        requires_disable: list[str] = []
        requires_disable_names: list[str] = []
        protected_dependents: list[str] = []
        for dependent_name in item.governance_state.dependent_plugins:
            dependent = next(
                (
                    candidate
                    for candidate in items
                    if dependent_name
                    in {
                        candidate.descriptor.name,
                        candidate.descriptor.module_name,
                    }
                ),
                None,
            )
            if dependent is None or not dependent.governance_state.is_global_enabled:
                continue
            if dependent.governance_state.is_protected:
                protected_dependents.append(
                    dependent.descriptor.name or dependent.descriptor.module_name,
                )
                continue
            requires_disable.append(dependent.descriptor.module_name)
            requires_disable_names.append(
                dependent.descriptor.name or dependent.descriptor.module_name,
            )

        blocked_reason = None
        if (
            item.governance_state.is_protected
            and item.governance_state.protected_reason
        ):
            blocked_reason = item.governance_state.protected_reason
        elif protected_dependents:
            blocked_reason = t(
                "common.required_by_plugins",
                plugins=", ".join(protected_dependents),
            )
        summary = (
            t("plugins.disabledAction")
            if not requires_disable_names
            else t(
                "common.required_by_plugins",
                plugins=", ".join(requires_disable_names),
            )
        )
        return PluginTogglePreview(
            module_name=item.descriptor.module_name,
            enabled=False,
            allowed=blocked_reason is None,
            summary=summary,
            blocked_reason=blocked_reason,
            requires_enable=[],
            requires_disable=requires_disable,
            protected_dependents=protected_dependents,
            missing_dependencies=[],
        )


plugin_toggle_service = PluginToggleService()
