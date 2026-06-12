from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from apeiria.db.base import Base
from apeiria.db.engine import close_engine, init_engine

if TYPE_CHECKING:
    from pathlib import Path


def test_access_and_group_repositories_use_new_database(
    tmp_path: Path,
) -> None:
    from apeiria.access.groups_repository import GroupStateRow, group_repository
    from apeiria.access.repository import access_repository

    db_path = tmp_path / "test.db"

    async def run() -> None:
        await init_engine(db_path)
        try:
            from apeiria.db.engine import get_engine

            async with get_engine().begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            await access_repository.upsert_access_rule(
                subject_type="group",
                subject_id="group-1",
                plugin_module="plugins.alpha",
                effect="deny",
                note="blocked",
            )
            rules = await access_repository.list_access_rules()
            assert len(rules) == 1
            assert rules[0].plugin_module == "plugins.alpha"
            assert rules[0].effect == "deny"

            await group_repository.save_group(
                GroupStateRow(
                    group_id="group-1",
                    group_name="Group One",
                    bot_status=False,
                    disabled_plugins='["plugins.alpha"]',
                )
            )
            assert await access_repository.get_group_bot_enabled("group-1") is False
            assert await access_repository.get_group_disabled_plugins("group-1") == [
                "plugins.alpha"
            ]
            group = await group_repository.get_group("group-1")
            assert group is not None
            assert group.group_name == "Group One"
            assert len(await group_repository.list_groups()) == 1
            assert (
                await access_repository.delete_access_rule(
                    subject_type="group",
                    subject_id="group-1",
                    plugin_module="plugins.alpha",
                )
                is True
            )
        finally:
            await close_engine()

    asyncio.run(run())
