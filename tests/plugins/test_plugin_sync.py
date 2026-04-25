from __future__ import annotations

import asyncio
import builtins
import importlib
import sys
from types import SimpleNamespace
from typing import Any


def test_plugin_sync_import_is_safe_without_nonebot_plugin_orm() -> None:
    original_import = builtins.__import__

    def guarded_import(
        name: str,
        globalns: dict[str, object] | None = None,
        localns: dict[str, object] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        if name == "nonebot_plugin_orm":
            raise AssertionError(name)
        return original_import(name, globalns, localns, fromlist, level)

    sys.modules.pop("apeiria.bot.hooks.plugin_sync", None)
    builtins.__import__ = guarded_import
    try:
        module = importlib.import_module("apeiria.bot.hooks.plugin_sync")
    finally:
        builtins.__import__ = original_import

    assert module.__name__ == "apeiria.bot.hooks.plugin_sync"


def test_plugin_sync_uses_sqlite_plugin_state_repository(monkeypatch: Any) -> None:
    from apeiria.bot.hooks import plugin_sync
    from apeiria.plugins import protection, repository

    calls: list[tuple[str, int, str]] = []

    class FakeRepository:
        async def ensure_plugin_policy(
            self,
            module_name: str,
            *,
            required_level: int = 0,
            protection_mode: str = "normal",
        ) -> None:
            calls.append((module_name, required_level, protection_mode))

    plugin = object()
    descriptor = SimpleNamespace(module_name="example.plugin", admin_level=3)

    monkeypatch.setattr(plugin_sync.nonebot, "get_loaded_plugins", lambda: [plugin])
    monkeypatch.setattr(
        plugin_sync.plugin_descriptor_builder,
        "build",
        lambda _: descriptor,
    )
    monkeypatch.setattr(
        protection,
        "get_default_protection_mode",
        lambda _: "protected",
    )
    monkeypatch.setattr(repository, "plugin_catalog_repository", FakeRepository())

    asyncio.run(plugin_sync.sync_plugins())

    assert calls == [("example.plugin", 3, "protected")]
