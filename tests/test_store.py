from __future__ import annotations

PLUGIN_RAW = {
    "module_name": "nonebot_plugin_status",
    "project_link": "nonebot-plugin-status",
    "name": "服务器状态查看",
    "desc": "通过戳一戳获取服务器状态",
    "author": "yanyongyu",
    "homepage": "https://github.com/nonebot/plugin-status",
    "tags": [{"label": "server", "color": "#aeeaa8"}],
    "is_official": True,
    "type": "application",
    "supported_adapters": None,
    "valid": True,
    "version": "0.9.0",
    "time": "2024-01-01T00:00:00Z",
}

ADAPTER_RAW = {
    "module_name": "nonebot.adapters.onebot.v11",
    "project_link": "nonebot-adapter-onebot",
    "name": "OneBot V11",
    "desc": "OneBot V11 协议",
    "author": "yanyongyu",
    "homepage": "https://onebot.adapters.nonebot.dev/",
    "tags": [],
    "is_official": True,
    "version": "2.4.6",
    "time": "2024-10-24T07:34:56.115315Z",
}


def test_parse_plugin_item_maps_real_registry_fields() -> None:
    from apeiria.web.store import _parse_item

    item = _parse_item(PLUGIN_RAW)

    assert item.name == "服务器状态查看"
    assert item.description == "通过戳一戳获取服务器状态"
    assert item.author == "yanyongyu"
    assert item.homepage == "https://github.com/nonebot/plugin-status"
    assert item.pypi_name == "nonebot-plugin-status"
    assert item.module_names == ["nonebot_plugin_status"]
    assert item.type == "application"
    assert item.tags == [{"label": "server", "color": "#aeeaa8"}]
    assert item.is_official is True
    assert item.version == "0.9.0"


def test_parse_plugin_pypi_name_never_falls_back_to_display_name() -> None:
    from apeiria.web.store import _parse_item

    item = _parse_item(PLUGIN_RAW)
    assert item.pypi_name != item.name
    assert item.pypi_name == "nonebot-plugin-status"


def test_parse_adapter_item_maps_real_registry_fields() -> None:
    from apeiria.web.store import _parse_item

    item = _parse_item(ADAPTER_RAW)

    assert item.name == "OneBot V11"
    assert item.description == "OneBot V11 协议"
    assert item.pypi_name == "nonebot-adapter-onebot"
    assert item.module_names == ["nonebot.adapters.onebot.v11"]
    assert item.is_official is True


def test_to_dict_includes_new_fields() -> None:
    from apeiria.web.store import _parse_item

    d = _parse_item(PLUGIN_RAW).to_dict()
    assert d["type"] == "application"
    assert d["tags"] == [{"label": "server", "color": "#aeeaa8"}]
    assert d["is_official"] is True
    assert d["pypi_name"] == "nonebot-plugin-status"


def test_registry_url_points_at_registry_host() -> None:
    from apeiria.web.store import _registry_url

    assert _registry_url("plugins") == "https://registry.nonebot.dev/plugins.json"
    assert _registry_url("adapters") == "https://registry.nonebot.dev/adapters.json"


def test_paginate_returns_slice_and_total() -> None:
    from apeiria.web.store import paginate

    items = list(range(10))
    page, total = paginate(items, offset=0, limit=3)
    assert page == [0, 1, 2]
    assert total == 10

    page, total = paginate(items, offset=9, limit=5)
    assert page == [9]
    assert total == 10


async def test_search_parses_and_filters(monkeypatch) -> None:
    from apeiria.web.store import NoneBotStoreSource

    source = NoneBotStoreSource()

    async def fake_fetch(kind: str) -> list[dict]:
        assert kind == "plugins"
        return [PLUGIN_RAW, {**PLUGIN_RAW, "name": "其它插件", "desc": "无关"}]

    monkeypatch.setattr(source, "_fetch", fake_fetch)

    all_items = await source.search("")
    assert len(all_items) == 2

    filtered = await source.search("服务器状态")
    assert len(filtered) == 1
    assert filtered[0].name == "服务器状态查看"


async def test_search_returns_empty_on_fetch_error(monkeypatch) -> None:
    from apeiria.web.store import NoneBotStoreSource

    source = NoneBotStoreSource()

    async def boom(_kind: str) -> list[dict]:
        msg = "network down"
        raise RuntimeError(msg)

    monkeypatch.setattr(source, "_fetch", boom)

    assert await source.search("anything") == []


async def test_search_adapters_uses_adapters_kind(monkeypatch) -> None:
    from apeiria.web.store import NoneBotStoreSource

    source = NoneBotStoreSource()
    seen = {}

    async def fake_fetch(kind: str) -> list[dict]:
        seen["kind"] = kind
        return [ADAPTER_RAW]

    monkeypatch.setattr(source, "_fetch", fake_fetch)

    items = await source.search_adapters("OneBot")
    assert seen["kind"] == "adapters"
    assert len(items) == 1
    assert items[0].pypi_name == "nonebot-adapter-onebot"
