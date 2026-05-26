"""Adapter selection read model for the Web UI."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.util import find_spec
from typing import TYPE_CHECKING, Literal

from apeiria.app.plugins.store.workflows import (
    PackageStoreListRequest,
    package_store_workflow,
)
from apeiria.config import adapter_config_service
from apeiria.plugins.registry import plugin_registration_config_service
from apeiria.plugins.settings_support import get_plugin_declared_configs

if TYPE_CHECKING:
    from apeiria.app.plugins.store.models import StoreItem
    from apeiria.plugins.registry import AdapterConfigStatus

AdapterSelectionState = Literal[
    "available",
    "installed",
    "enabled_pending_restart",
    "enabled_loaded",
    "unavailable",
]


@dataclass(frozen=True, slots=True)
class AdapterSelectionItem:
    """One adapter entry normalized for project selection UI."""

    module_name: str
    display_name: str
    source_id: str | None = None
    source_name: str | None = None
    adapter_id: str | None = None
    package_name: str | None = None
    description: str | None = None
    homepage: str | None = None
    project_link: str | None = None
    tags: list[str] | None = None
    is_official: bool = False
    is_installed: bool = False
    is_enabled: bool = False
    is_loaded: bool = False
    is_importable: bool = False
    is_configurable: bool = False
    installed_package: str | None = None
    installed_module_names: list[str] | None = None
    can_update: bool = False
    state: AdapterSelectionState = "available"


@dataclass(frozen=True, slots=True)
class AdapterSelectionSummary:
    """Summary counts for the adapter selection surface."""

    enabled: int
    loaded: int
    unavailable: int
    restart_required: int


@dataclass(frozen=True, slots=True)
class AdapterSelectionStateView:
    """Complete adapter selection state for one Web UI read."""

    enabled_adapters: list[AdapterSelectionItem]
    candidates: list[AdapterSelectionItem]
    summary: AdapterSelectionSummary
    total_candidates: int
    page: int
    per_page: int


@dataclass(frozen=True, slots=True)
class AdapterSelectionRequest:
    """Selection query options."""

    search: str = ""
    source: str = ""
    category: str = ""
    sort: str = "default"
    unenabled_only: bool = False
    page: int = 1
    per_page: int = 16


class AdapterSelectionService:
    """Compose adapter config, runtime status, and store items."""

    async def get_selection(
        self,
        request: AdapterSelectionRequest | None = None,
    ) -> AdapterSelectionStateView:
        query = request or AdapterSelectionRequest()
        config_state = plugin_registration_config_service.get_adapter_config()
        config = adapter_config_service.read_project_adapter_config()
        module_to_package = {
            module_name: package_name
            for package_name, module_names in config["packages"].items()
            for module_name in module_names
        }
        enabled_by_name = {item.name: item for item in config_state.modules}
        store_page = await package_store_workflow.list_items(
            PackageStoreListRequest(
                item_type="adapter",
                source_id=query.source,
                keyword=query.search,
                category=query.category,
                sort=query.sort,
                page=query.page,
                page_size=query.per_page,
            )
        )
        store_by_module = {item.module_name: item for item in store_page.items}
        enabled_items = [
            self._from_enabled_adapter(
                status,
                store_by_module.get(status.name),
                module_to_package.get(status.name),
            )
            for status in config_state.modules
        ]
        candidate_items = [
            self._from_store_item(item, enabled_by_name.get(item.module_name))
            for item in store_page.items
            if not query.unenabled_only or item.module_name not in enabled_by_name
        ]
        return AdapterSelectionStateView(
            enabled_adapters=enabled_items,
            candidates=candidate_items,
            summary=AdapterSelectionSummary(
                enabled=len(enabled_items),
                loaded=sum(1 for item in enabled_items if item.is_loaded),
                unavailable=sum(1 for item in enabled_items if not item.is_importable),
                restart_required=sum(
                    1
                    for item in enabled_items
                    if item.is_importable and not item.is_loaded
                ),
            ),
            total_candidates=store_page.total,
            page=store_page.page,
            per_page=store_page.per_page,
        )

    def enable_adapter(self, module_name: str) -> AdapterSelectionItem:
        normalized = module_name.strip()
        if not normalized:
            msg = "adapter module is required"
            raise ValueError(msg)
        config_state = plugin_registration_config_service.update_adapter_config(
            [
                *(
                    item.name
                    for item in (
                        plugin_registration_config_service.get_adapter_config().modules
                    )
                ),
                normalized,
            ]
        )
        status = next(item for item in config_state.modules if item.name == normalized)
        return self._from_enabled_adapter(status, None, None)

    def disable_adapter(self, module_name: str) -> AdapterSelectionItem | None:
        normalized = module_name.strip()
        current = plugin_registration_config_service.get_adapter_config()
        previous = {item.name: item for item in current.modules}.get(normalized)
        if previous is None:
            return None
        plugin_registration_config_service.update_adapter_config(
            [item.name for item in current.modules if item.name != normalized]
        )
        return AdapterSelectionItem(
            module_name=previous.name,
            display_name=_display_name(previous.name),
            is_installed=previous.is_importable,
            is_enabled=False,
            is_loaded=previous.is_loaded,
            is_importable=previous.is_importable,
            is_configurable=_module_is_configurable(previous.name)
            if previous.is_importable
            else False,
            state="installed" if previous.is_importable else "available",
        )

    def _from_enabled_adapter(
        self,
        status: "AdapterConfigStatus",
        store_item: "StoreItem | None",
        installed_package: str | None,
    ) -> AdapterSelectionItem:
        package_name = installed_package or (
            store_item.package_name if store_item else None
        )
        return AdapterSelectionItem(
            source_id=store_item.source_id if store_item else None,
            source_name=store_item.source_name if store_item else None,
            adapter_id=store_item.item_id if store_item else None,
            module_name=status.name,
            display_name=store_item.name if store_item else _display_name(status.name),
            package_name=package_name,
            description=store_item.description if store_item else None,
            homepage=store_item.homepage if store_item else None,
            project_link=store_item.project_link if store_item else None,
            tags=list(store_item.tags) if store_item else [],
            is_official=store_item.is_official if store_item else False,
            is_installed=status.is_importable,
            is_enabled=True,
            is_loaded=status.is_loaded,
            is_importable=status.is_importable,
            is_configurable=_module_is_configurable(status.name),
            installed_package=installed_package
            or (store_item.installed_package if store_item else None),
            installed_module_names=(
                list(store_item.installed_module_names) if store_item else []
            ),
            can_update=store_item.can_update if store_item else False,
            state=_state_for(
                is_enabled=True,
                is_installed=status.is_importable,
                is_loaded=status.is_loaded,
                is_importable=status.is_importable,
            ),
        )

    def _from_store_item(
        self,
        item: "StoreItem",
        status: "AdapterConfigStatus | None",
    ) -> AdapterSelectionItem:
        enabled = status is not None
        importable = (
            status.is_importable if status else _module_is_importable(item.module_name)
        )
        loaded = status.is_loaded if status else False
        installed = item.is_installed or importable
        return AdapterSelectionItem(
            source_id=item.source_id,
            source_name=item.source_name,
            adapter_id=item.item_id,
            module_name=item.module_name,
            display_name=item.name or _display_name(item.module_name),
            package_name=item.package_name,
            description=item.description,
            homepage=item.homepage,
            project_link=item.project_link,
            tags=list(item.tags),
            is_official=item.is_official,
            is_installed=installed,
            is_enabled=enabled,
            is_loaded=loaded,
            is_importable=importable,
            is_configurable=_module_is_configurable(item.module_name)
            if importable
            else False,
            installed_package=item.installed_package,
            installed_module_names=list(item.installed_module_names),
            can_update=item.can_update,
            state=_state_for(
                is_enabled=enabled,
                is_installed=installed,
                is_loaded=loaded,
                is_importable=importable,
            ),
        )


def _state_for(
    *,
    is_enabled: bool,
    is_installed: bool,
    is_loaded: bool,
    is_importable: bool,
) -> AdapterSelectionState:
    if is_enabled and not is_importable:
        return "unavailable"
    if is_enabled and is_loaded:
        return "enabled_loaded"
    if is_enabled:
        return "enabled_pending_restart"
    if is_installed:
        return "installed"
    return "available"


def _module_is_importable(module_name: str) -> bool:
    try:
        return find_spec(module_name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def _module_is_configurable(module_name: str) -> bool:
    try:
        return get_plugin_declared_configs(module_name).has_config_model
    except Exception:  # noqa: BLE001
        return False


def _display_name(module_name: str) -> str:
    return module_name.rsplit(".", maxsplit=1)[-1] or module_name


adapter_selection_service = AdapterSelectionService()


__all__ = [
    "AdapterSelectionItem",
    "AdapterSelectionRequest",
    "AdapterSelectionService",
    "AdapterSelectionState",
    "AdapterSelectionStateView",
    "AdapterSelectionSummary",
    "adapter_selection_service",
]
