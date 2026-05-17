from __future__ import annotations

import sys
from types import ModuleType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest


def test_load_framework_skips_disabled_ai_builtin_plugin(
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    import apeiria._framework_loader as loader

    loaded_builtin_plugins: list[str] = []
    loaded_plugins: list[str] = []
    hooks_registered = False

    def fake_load_builtin_plugins(*names: str) -> None:
        loaded_builtin_plugins.extend(names)

    def fake_load_plugin(name: str) -> None:
        loaded_plugins.append(name)

    def fake_disabled_modules(modules: tuple[str, ...]) -> set[str]:
        assert "apeiria.builtin_plugins.ai" in modules
        return {"apeiria.builtin_plugins.ai"}

    def fake_register_bot_hooks() -> None:
        nonlocal hooks_registered
        hooks_registered = True

    fake_registry = ModuleType("apeiria.bot.hooks.registry")
    fake_registry.register_bot_hooks = fake_register_bot_hooks  # type: ignore[attr-defined]

    monkeypatch.setattr(
        loader.nonebot,
        "load_builtin_plugins",
        fake_load_builtin_plugins,
    )
    monkeypatch.setattr(loader.nonebot, "load_plugin", fake_load_plugin)
    monkeypatch.setattr("apeiria.log.setup_logging", lambda: None)
    monkeypatch.setattr("apeiria.db.schema.ensure_database_ready_sync", lambda: None)
    monkeypatch.setattr(
        "apeiria.plugins.state.get_disabled_plugin_modules_sync",
        fake_disabled_modules,
    )
    monkeypatch.setitem(sys.modules, "apeiria.bot.hooks.registry", fake_registry)

    loader.load_framework()

    assert loaded_builtin_plugins == ["echo"]
    assert "nonebot_plugin_alconna" in loaded_plugins
    assert "apeiria.builtin_plugins.ai" not in loaded_plugins
    assert "apeiria.builtin_plugins.web_ui" in loaded_plugins
    assert hooks_registered is True
