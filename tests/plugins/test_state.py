from __future__ import annotations

import asyncio
import sys
from typing import TYPE_CHECKING

from apeiria.db.runtime import database_runtime

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import MonkeyPatch


def test_get_disabled_plugin_modules_reads_from_new_database(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    from apeiria.db.base import Base
    from apeiria.db.engine import close_engine, get_engine, init_engine
    from apeiria.plugins.repository import plugin_catalog_repository
    from apeiria.plugins.state import get_disabled_plugin_modules

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
            await plugin_catalog_repository.set_plugin_enabled(
                "plugins.beta",
                enabled=False,
            )

            disabled = await get_disabled_plugin_modules()

            assert disabled == {"plugins.beta"}
        finally:
            await close_engine()

    asyncio.run(run())


def test_is_module_importable_does_not_import_parent_plugin_module() -> None:
    from apeiria.plugins.metadata import module_cache

    module_cache.invalidate_module_discovery_caches()
    sys.modules.pop("nonebot_plugin_alconna", None)
    sys.modules.pop("nonebot_plugin_alconna.uniseg", None)

    assert module_cache.is_module_importable("nonebot_plugin_alconna.uniseg") is True
    assert "nonebot_plugin_alconna" not in sys.modules
    assert "nonebot_plugin_alconna.uniseg" not in sys.modules
