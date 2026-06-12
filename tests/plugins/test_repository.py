from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from apeiria.db.base import Base
from apeiria.db.engine import close_engine, get_engine, init_engine
from apeiria.db.runtime import database_runtime

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import MonkeyPatch


def test_plugin_repository_persists_enabled_state_and_policy(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    from apeiria.plugins.repository import plugin_catalog_repository

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    db_path = tmp_path / "data" / "db" / "apeiria.sqlite3"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    async def run() -> None:
        await init_engine(db_path)
        try:
            async with get_engine().begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            await plugin_catalog_repository.ensure_plugin_record_by_module_name(
                "plugins.alpha"
            )
            assert (
                await plugin_catalog_repository.get_plugin_enabled("plugins.alpha")
                is True
            )

            changed = await plugin_catalog_repository.set_plugin_enabled(
                "plugins.alpha",
                enabled=False,
            )
            assert changed is True
            assert (
                await plugin_catalog_repository.get_plugin_enabled("plugins.alpha")
                is False
            )

            await plugin_catalog_repository.ensure_plugin_policy(
                "plugins.alpha",
                access_mode="default_deny",
                protection_mode="required",
            )
            policy = await plugin_catalog_repository.get_plugin_policy("plugins.alpha")
            enabled_map = await plugin_catalog_repository.get_enabled_map()
            info_map = await plugin_catalog_repository.get_plugin_info_map()

            assert policy is not None
            assert policy.plugin_module == "plugins.alpha"
            assert policy.access_mode == "default_deny"
            assert policy.protection_mode == "required"
            assert enabled_map == {"plugins.alpha": False}
            assert info_map["plugins.alpha"].module_name == "plugins.alpha"
            assert info_map["plugins.alpha"].is_global_enabled is False
        finally:
            await close_engine()

    asyncio.run(run())


def test_plugin_repository_deletes_only_existing_plugin_records(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    from apeiria.plugins.repository import plugin_catalog_repository

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    db_path = tmp_path / "data" / "db" / "apeiria.sqlite3"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    async def run() -> None:
        await init_engine(db_path)
        try:
            async with get_engine().begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            await plugin_catalog_repository.ensure_plugin_record_by_module_name(
                "plugins.alpha"
            )
            await plugin_catalog_repository.ensure_plugin_record_by_module_name(
                "plugins.beta"
            )

            removed = plugin_catalog_repository.delete_plugin_records_sync(
                ["plugins.beta", "plugins.missing", "plugins.beta"]
            )
            assert removed == ["plugins.beta"]
            assert plugin_catalog_repository.get_persisted_plugin_modules_sync() == {
                "plugins.alpha"
            }
        finally:
            await close_engine()

    asyncio.run(run())
