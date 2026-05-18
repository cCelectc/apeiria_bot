from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from apeiria.app.plugins.install_resolution import (
    PluginInstallResolutionService,
    PluginInstallSource,
)
from apeiria.app.plugins.store.models import StoreItem

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_requirement_resolution_returns_ambiguous_candidates(
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    monkeypatch.setattr(
        "apeiria.app.plugins.install_resolution.resolve_plugin_module_candidates_from_requirement",
        lambda _: ["nonebot_plugin_a", "nonebot_plugin_b"],
    )
    monkeypatch.setattr(
        "apeiria.app.plugins.install_resolution.plugin_config_service.read_project_plugin_config",
        lambda: {"modules": [], "dirs": [], "packages": {}},
    )

    result = asyncio.run(
        PluginInstallResolutionService().resolve(
            PluginInstallSource(kind="requirement", value="nonebot-plugin-bundle")
        )
    )

    assert result.status == "ambiguous"
    assert [item.module_name for item in result.candidates] == [
        "nonebot_plugin_a",
        "nonebot_plugin_b",
    ]
    assert result.default_action is None


def test_requirement_resolution_requires_advanced_module_when_unresolved(
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    monkeypatch.setattr(
        "apeiria.app.plugins.install_resolution.resolve_plugin_module_candidates_from_requirement",
        lambda _: [],
    )

    result = asyncio.run(
        PluginInstallResolutionService().resolve(
            PluginInstallSource(kind="requirement", value="unknown-plugin")
        )
    )

    assert result.status == "unresolved"
    assert result.candidates == []
    assert result.default_action is None


def test_store_item_resolution_uses_store_metadata(
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    async def fake_get_item(request: Any) -> StoreItem:
        assert request.item_type == "plugin"
        assert request.source_id == "official"
        assert request.item_id == "weather"
        return StoreItem(
            source_id="official",
            source_label="Official",
            item_id="weather",
            type="plugin",
            name="Weather",
            module_name="nonebot_plugin_weather",
            package_requirement="nonebot-plugin-weather",
        )

    monkeypatch.setattr(
        "apeiria.app.plugins.install_resolution.package_store_workflow.get_item",
        fake_get_item,
    )

    result = asyncio.run(
        PluginInstallResolutionService().resolve(
            PluginInstallSource(
                kind="store_item",
                source_id="official",
                item_id="weather",
            )
        )
    )

    assert result.status == "resolved"
    assert result.candidates[0].module_name == "nonebot_plugin_weather"
    assert result.default_action is not None
    assert result.default_action.requirement == "nonebot-plugin-weather"
    assert result.default_action.module_name == "nonebot_plugin_weather"


def test_local_file_path_resolves_to_module(
    monkeypatch: "pytest.MonkeyPatch",
    tmp_path: "Path",
) -> None:
    plugin_file = tmp_path / "local_plugin.py"
    plugin_file.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        "apeiria.app.plugins.install_resolution.current_project_root",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "apeiria.app.plugins.install_resolution.plugin_config_service.read_project_plugin_config",
        lambda: {"modules": [], "dirs": [], "packages": {}},
    )

    result = asyncio.run(
        PluginInstallResolutionService().resolve(
            PluginInstallSource(kind="local_path", value="local_plugin.py")
        )
    )

    assert result.status == "resolved"
    assert result.candidates[0].module_name == "local_plugin"
    assert result.default_action is not None
    assert result.default_action.kind == "register_local_module"


def test_local_directory_without_init_resolves_to_directory(
    monkeypatch: "pytest.MonkeyPatch",
    tmp_path: "Path",
) -> None:
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()
    monkeypatch.setattr(
        "apeiria.app.plugins.install_resolution.current_project_root",
        lambda: tmp_path,
    )

    result = asyncio.run(
        PluginInstallResolutionService().resolve(
            PluginInstallSource(kind="local_path", value="plugins")
        )
    )

    assert result.status == "resolved"
    assert result.candidates == []
    assert result.default_action is not None
    assert result.default_action.kind == "register_local_directory"
    assert result.default_action.path == "plugins"
