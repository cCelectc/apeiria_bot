from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from apeiria.app.plugins.store.models import (
    StoreItem,
    StorePage,
    StoreQuery,
    StoreSource,
)
from apeiria.app.plugins.store.service import StoreService

if TYPE_CHECKING:
    from pytest import MonkeyPatch


class _FakeSource:
    def __init__(self, items: list[StoreItem]) -> None:
        self._items = items

    def source_info(self) -> StoreSource:
        return StoreSource(
            source_id="official",
            label="Official",
            kind="builtin",
        )

    async def list_page(self, query: StoreQuery) -> StorePage:
        items = [item for item in self._items if item.type == query.type]
        return StorePage(
            items=items,
            total=len(items),
            page=query.page,
            page_size=query.page_size,
        )

    async def find_exact(
        self,
        item_type: str,
        plugin_id: str,
    ) -> StoreItem | None:
        for item in self._items:
            if item.type == item_type and item.item_id == plugin_id:
                return item
        return None

    def resolve_install_candidate(self, _item: StoreItem) -> None:
        return None


def test_store_service_enriches_adapter_items_with_project_state(
    monkeypatch: MonkeyPatch,
) -> None:
    item = StoreItem(
        source_id="official",
        item_id="console",
        type="adapter",
        name="Console Adapter",
        module_name="nonebot.adapters.console",
        package_requirement="nonebot-adapter-console",
    )
    service = StoreService(sources=[_FakeSource([item])])

    monkeypatch.setattr(
        "apeiria.app.plugins.store.service.adapter_config_service.read_project_adapter_config",
        lambda: {
            "modules": ["nonebot.adapters.console"],
            "packages": {
                "nonebot-adapter-console": ["nonebot.adapters.console"],
            },
        },
    )
    monkeypatch.setattr(
        "apeiria.app.plugins.store.service.nonebot.get_adapters",
        lambda: {
            "Console": type(
                "ConsoleAdapter",
                (),
                {"__module__": "nonebot.adapters.console.adapter"},
            )
        },
    )

    result = asyncio.run(service.list_items(StoreQuery(type="adapter")))

    assert result.total == 1
    assert result.items[0].is_installed is True
    assert result.items[0].is_registered is True
    assert result.items[0].installed_package == "nonebot-adapter-console"
    assert result.items[0].installed_module_names == ["nonebot.adapters.console"]
    assert result.items[0].can_update is True


def test_store_service_deduplicates_adapter_items_from_same_source(
    monkeypatch: MonkeyPatch,
) -> None:
    item = StoreItem(
        source_id="official",
        item_id="console",
        type="adapter",
        name="Console Adapter",
        module_name="nonebot.adapters.console",
        package_requirement="nonebot-adapter-console",
    )
    duplicate = StoreItem(
        source_id="official",
        item_id="console-duplicate",
        type="adapter",
        name="Console Adapter Duplicate",
        module_name="nonebot.adapters.console",
        package_requirement="nonebot-adapter-console",
    )
    service = StoreService(sources=[_FakeSource([item, duplicate])])

    monkeypatch.setattr(
        "apeiria.app.plugins.store.service.adapter_config_service.read_project_adapter_config",
        lambda: {
            "modules": [],
            "packages": {},
        },
    )
    monkeypatch.setattr(
        "apeiria.app.plugins.store.service.nonebot.get_adapters",
        dict,
    )

    result = asyncio.run(service.list_items(StoreQuery(type="adapter")))

    assert result.total == 1
    assert result.items[0].item_id == "console"
