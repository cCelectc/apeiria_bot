from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from tests.db_helpers import async_db

if TYPE_CHECKING:
    from pathlib import Path


def test_access_and_group_repositories_use_new_database(
    tmp_path: Path,
) -> None:
    from apeiria.access.groups_repository import GroupStateRow, group_repository
    from apeiria.access.repository import access_repository

    db_path = tmp_path / "test.db"

    async def run() -> None:
        async with async_db(db_path):
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

    asyncio.run(run())
