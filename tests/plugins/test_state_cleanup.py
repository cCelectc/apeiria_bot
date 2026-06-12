from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Protocol

from apeiria.db.runtime import database_runtime
from tests.db_helpers import async_db

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import MonkeyPatch


class _PluginRecordRepository(Protocol):
    async def ensure_plugin_record_by_module_name(self, module_name: str) -> None: ...


def test_cleanup_orphan_plugin_state_removes_only_true_orphans(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    from apeiria.plugins.repository import plugin_catalog_repository
    from apeiria.plugins.state_cleanup import plugin_state_cleanup_service

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    monkeypatch.chdir(tmp_path)
    database_runtime.ensure_ready()
    _write_plugin_config(
        tmp_path,
        modules=[
            "plugins.explicit",
        ],
    )

    db_path = tmp_path / "data" / "db" / "apeiria.sqlite3"

    async def run() -> None:
        async with async_db(db_path):
            await _ensure_records(
                plugin_catalog_repository,
                [
                    "plugins.orphan",
                    "plugins.explicit",
                    "apeiria.builtin_plugins.admin",
                    "importlib",
                    "plugins.pending",
                    "nonebot_plugin_waiter",
                ],
            )

    asyncio.run(run())

    removed = plugin_state_cleanup_service.cleanup_orphan_plugin_state(
        pending_uninstall_modules={"plugins.pending"}
    )

    assert removed == ["importlib", "plugins.orphan"]
    assert plugin_catalog_repository.get_persisted_plugin_modules_sync() == {
        "apeiria.builtin_plugins.admin",
        "nonebot_plugin_waiter",
        "plugins.explicit",
        "plugins.pending",
    }


def test_cleanup_orphan_plugin_state_removes_importable_unreferenced_module(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    from apeiria.plugins.repository import plugin_catalog_repository
    from apeiria.plugins.state_cleanup import plugin_state_cleanup_service

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    monkeypatch.chdir(tmp_path)
    database_runtime.ensure_ready()
    _write_plugin_config(tmp_path, modules=["nonebot_plugin_parser"])

    db_path = tmp_path / "data" / "db" / "apeiria.sqlite3"

    async def run() -> None:
        async with async_db(db_path):
            await _ensure_records(
                plugin_catalog_repository,
                [
                    "nonebot.plugins.echo",
                    "nonebot_plugin_parser",
                ],
            )

    asyncio.run(run())

    removed = plugin_state_cleanup_service.cleanup_orphan_plugin_state()

    assert removed == ["nonebot.plugins.echo"]
    assert plugin_catalog_repository.get_persisted_plugin_modules_sync() == {
        "nonebot_plugin_parser"
    }


def test_cleanup_orphan_plugin_state_is_noop_when_all_rows_are_valid(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    from apeiria.plugins.repository import plugin_catalog_repository
    from apeiria.plugins.state_cleanup import plugin_state_cleanup_service

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    monkeypatch.chdir(tmp_path)
    database_runtime.ensure_ready()
    _write_plugin_config(tmp_path, modules=["plugins.explicit"])

    db_path = tmp_path / "data" / "db" / "apeiria.sqlite3"

    async def run() -> None:
        async with async_db(db_path):
            await _ensure_records(
                plugin_catalog_repository,
                [
                    "plugins.explicit",
                    "apeiria.builtin_plugins.help",
                ],
            )

    asyncio.run(run())

    removed = plugin_state_cleanup_service.cleanup_orphan_plugin_state()

    assert removed == []
    assert plugin_catalog_repository.get_persisted_plugin_modules_sync() == {
        "apeiria.builtin_plugins.help",
        "plugins.explicit",
    }


def _write_plugin_config(project_root: Path, *, modules: list[str]) -> None:
    rendered_modules = ", ".join(f'"{module}"' for module in modules)
    path = project_root / "apeiria.plugins.toml"
    path.write_text(
        "\n".join(
            [
                "[plugins]",
                f"modules = [{rendered_modules}]",
                "dirs = []",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


async def _ensure_records(
    repository: _PluginRecordRepository,
    module_names: list[str],
) -> None:
    for module_name in module_names:
        await repository.ensure_plugin_record_by_module_name(module_name)
