from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any


def test_plugin_sync_uses_sqlite_plugin_state_repository(monkeypatch: Any) -> None:
    from apeiria.bot.hooks import plugin_sync
    from apeiria.plugins import protection, repository

    calls: list[tuple[str, str]] = []

    class FakeRepository:
        async def ensure_plugin_policy(
            self,
            module_name: str,
            *,
            protection_mode: str = "normal",
        ) -> None:
            calls.append((module_name, protection_mode))

    plugin = object()
    descriptor = SimpleNamespace(module_name="example.plugin")

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

    assert calls == [("example.plugin", "protected")]
