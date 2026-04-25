from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from apeiria.db.runtime import database_runtime

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import MonkeyPatch


def test_get_disabled_plugin_modules_reads_from_new_database(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    from apeiria.plugins.repository import plugin_catalog_repository
    from apeiria.plugins.state import get_disabled_plugin_modules

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    async def run() -> None:
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

    asyncio.run(run())
