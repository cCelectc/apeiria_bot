"""Operations-plane store service."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from apeiria.config.plugins import plugin_config_service
from apeiria.plugins.package_ids import normalize_package_id
from apeiria.plugins.store.models import (
    StoreCategoryCount,
    StoreInstallCandidate,
    StoreItem,
    StoreItemType,
    StorePage,
    StoreQuery,
    StoreSource,
)
from apeiria.plugins.store.sources import (
    StoreSourceAdapter,
    configured_store_sources,
)


class StoreService:
    """Store aggregation and normalization service."""

    def __init__(self, sources: list[StoreSourceAdapter] | None = None) -> None:
        self._sources_override = sources
        self._sources_cache: list[StoreSourceAdapter] | None = (
            list(sources) if sources is not None else None
        )

    def _sources(self) -> list[StoreSourceAdapter]:
        if self._sources_cache is None:
            self._sources_cache = configured_store_sources()
        self._sources_cache.sort(key=lambda source: source.source_info().priority)
        return self._sources_cache

    def _reload_configured_sources(self) -> list[StoreSourceAdapter]:
        if self._sources_override is not None:
            return self._sources()

        previous = {
            source.source_info().source_id: source for source in self._sources()
        }
        reloaded = configured_store_sources()
        preserved: list[StoreSourceAdapter] = []
        for source in reloaded:
            source_id = source.source_info().source_id
            preserved.append(previous.get(source_id, source))
        self._sources_cache = preserved
        return self._sources()

    def list_sources(self) -> list[StoreSource]:
        return [source.source_info() for source in self._sources()]

    async def refresh_sources(
        self,
        *,
        item_type: StoreItemType = "plugin",
        source_id: str = "",
    ) -> list[StoreSource]:
        for source in self._reload_configured_sources():
            source_info = source.source_info()
            if source_id and source_info.source_id != source_id:
                continue
            try:
                await source.list_page(StoreQuery(type=item_type, source_id=source_id))
            except Exception:  # noqa: BLE001
                continue
        return self.list_sources()

    async def list_items(self, query: StoreQuery | None = None) -> StorePage:
        effective_query = query or StoreQuery()
        source_pages = await self._load_source_pages(effective_query)
        plugin_state = (
            await _plugin_state() if effective_query.type == "plugin" else None
        )
        enriched_items = self._enrich_item_state(
            [item for page in source_pages for item in page.items],
            effective_query,
            plugin_state,
        )
        categories = _collect_categories(enriched_items)
        items = _apply_category_filter(enriched_items, effective_query.category)
        if effective_query.sort != "default":
            items.sort(key=_item_sort_key(effective_query.sort))

        total = len(items)
        page_size = max(1, min(effective_query.page_size, 100))
        page = max(1, effective_query.page)
        start = (page - 1) * page_size
        end = start + page_size
        return StorePage(
            items=items[start:end],
            total=total,
            page=page,
            page_size=page_size,
            has_next=end < total,
            categories=categories,
        )

    async def get_item(
        self,
        *,
        source_id: str,
        plugin_id: str,
        item_type: StoreItemType = "plugin",
    ) -> StoreItem | None:
        source = self._get_source(source_id)
        if source is None:
            return None
        item = await source.find_exact(item_type, plugin_id)
        if item is None:
            return None
        plugin_state = await _plugin_state() if item_type == "plugin" else None
        enriched = self._enrich_item_state(
            [item],
            StoreQuery(type=item_type),
            plugin_state,
        )
        return enriched[0] if enriched else None

    async def resolve_install_candidate(
        self,
        *,
        source_id: str,
        plugin_id: str,
        item_type: StoreItemType = "plugin",
    ) -> StoreInstallCandidate | None:
        item = await self.get_item(
            source_id=source_id,
            plugin_id=plugin_id,
            item_type=item_type,
        )
        if item is None:
            return None
        source = self._get_source(source_id)
        if source is None:
            return None
        return source.resolve_install_candidate(item)

    async def _load_source_pages(self, query: StoreQuery) -> list[StorePage]:
        pages: list[StorePage] = []
        for source in self._sources():
            source_info = source.source_info()
            if query.source_id and source_info.source_id != query.source_id:
                continue
            pages.append(await source.list_page(query))
        return pages

    def _enrich_item_state(
        self,
        items: list[StoreItem],
        query: StoreQuery,
        plugin_state: "_PluginState | None",
    ) -> list[StoreItem]:
        if query.type != "plugin":
            return [item for item in items if _match_item(item, query)]

        return [
            item
            for item in (
                _enrich_plugin_item_state(item, plugin_state) for item in items
            )
            if _match_item(item, query)
        ]

    def _get_source(self, source_id: str) -> StoreSourceAdapter | None:
        for source in self._sources():
            if source.source_info().source_id == source_id:
                return source
        return None


def _enrich_plugin_item_state(
    item: StoreItem,
    plugin_state: "_PluginState | None",
) -> StoreItem:
    if plugin_state is None:
        return item
    installed = (
        item.module_name in plugin_state.loaded_module_names
        or item.module_name in plugin_state.registered_module_names
    )
    registered = item.module_name in plugin_state.registered_module_names
    installed_package = plugin_state.module_to_package.get(item.module_name)
    normalized_installed = normalize_package_id(installed_package or "")
    normalized_store = normalize_package_id(item.package_requirement)
    return replace(
        item,
        is_installed=installed,
        is_registered=registered,
        installed_package=installed_package,
        installed_module_names=plugin_state.package_bindings.get(
            installed_package or "",
            [],
        ),
        can_update=(
            registered
            and bool(normalized_installed)
            and normalized_installed == normalized_store
        ),
    )


class _PluginState:
    def __init__(
        self,
        *,
        loaded_module_names: set[str],
        registered_module_names: set[str],
        package_bindings: dict[str, list[str]],
        module_to_package: dict[str, str],
    ) -> None:
        self.loaded_module_names = loaded_module_names
        self.registered_module_names = registered_module_names
        self.package_bindings = package_bindings
        self.module_to_package = module_to_package


async def _plugin_state() -> _PluginState:
    project_config = plugin_config_service.read_project_plugin_config()
    registered_module_names = set(project_config["modules"])
    package_bindings = project_config["packages"]
    module_to_package = {
        module_name: package_name
        for package_name, module_names in package_bindings.items()
        for module_name in module_names
    }
    try:
        from apeiria.plugins import plugin_governance_service

        loaded_plugins = await plugin_governance_service.list_plugins()
        loaded_module_names = {item.descriptor.module_name for item in loaded_plugins}
    except ValueError:
        loaded_module_names = set()

    return _PluginState(
        loaded_module_names=loaded_module_names,
        registered_module_names=registered_module_names,
        package_bindings=package_bindings,
        module_to_package=module_to_package,
    )


def _match_item(item: StoreItem, query: StoreQuery) -> bool:
    if query.installed_only and not item.is_installed:
        return False
    if query.uninstalled_only and item.is_installed:
        return False

    keyword = query.keyword.strip().lower()
    if not keyword:
        return True

    haystack = " ".join(
        [
            item.name,
            item.module_name,
            item.package_requirement,
            item.desc or "",
            item.author or "",
            " ".join(item.tags),
        ]
    ).lower()
    return keyword in haystack


def _item_sort_key(sort_mode: str):
    if sort_mode == "name":
        return lambda item: (item.name.lower(), item.module_name.lower())
    if sort_mode == "updated":
        return lambda item: (
            -_timestamp_value(item.publish_time),
            item.name.lower(),
            item.module_name.lower(),
        )
    return lambda item: (item.name.lower(), item.module_name.lower())


def _timestamp_value(value: str | None) -> int:
    if not value:
        return 0
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        return int(datetime.fromisoformat(normalized).timestamp())
    except ValueError:
        return 0


def _apply_category_filter(
    items: list[StoreItem],
    category: str,
) -> list[StoreItem]:
    if not category:
        return items
    return [item for item in items if category in item.tags]


def _collect_categories(items: list[StoreItem]) -> list[StoreCategoryCount]:
    counts: dict[str, int] = {}
    for item in items:
        for tag in item.tags:
            counts[tag] = counts.get(tag, 0) + 1
    return [
        StoreCategoryCount(value=value, count=count)
        for value, count in sorted(
            counts.items(),
            key=lambda entry: (-entry[1], entry[0].lower()),
        )
    ]


store_service = StoreService()
