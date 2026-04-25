from __future__ import annotations

import asyncio
import builtins
import importlib
import sys
from types import SimpleNamespace
from typing import TYPE_CHECKING

from apeiria.db.runtime import database_runtime

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import MonkeyPatch


def test_statistics_import_is_safe_without_nonebot_plugin_orm() -> None:
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

    sys.modules.pop("apeiria.utils.statistics", None)
    builtins.__import__ = guarded_import
    try:
        module = importlib.import_module("apeiria.utils.statistics")
    finally:
        builtins.__import__ = original_import

    assert module.__name__ == "apeiria.utils.statistics"


def test_statistics_records_to_sqlite(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    from apeiria.utils.statistics import StatisticsService

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    plugin = SimpleNamespace(module_name="example.plugin", name="Example")
    matcher = SimpleNamespace(
        plugin=plugin,
        state={"_prefix": {"command": ("hello", "world")}},
    )
    event = SimpleNamespace(
        get_user_id=lambda: "user-1",
        get_session_id=lambda: "user-1",
    )

    asyncio.run(
        StatisticsService().record_matcher_execution(
            matcher,  # type: ignore[arg-type]
            event,  # type: ignore[arg-type]
            success=False,
        )
    )

    with database_runtime.connect_sync() as connection:
        row = connection.execute(
            """
            SELECT plugin_name, command, user_id, group_id, success
            FROM command_statistics
            """
        ).fetchone()

    assert row == ("example.plugin", "hello world", "user-1", None, 0)
