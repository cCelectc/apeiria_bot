"""Group application services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeiria.app.groups.repository import group_repository
from apeiria.shared.group_state import decode_disabled_plugins
from apeiria.shared.plugin_introspection import get_plugin_protection_reason

if TYPE_CHECKING:
    from apeiria.infra.db.models.group import GroupConsole


@dataclass(frozen=True)
class GroupRecord:
    """Normalized group record for interfaces."""

    group_id: str
    group_name: str | None
    bot_status: bool
    disabled_plugins: list[str]


class GroupService:
    """Manage persisted per-group settings."""

    async def get_group(self, group_id: str) -> GroupRecord | None:
        row = await group_repository.get_group(group_id)
        if row is None:
            return None
        return self._to_record(row)

    async def list_groups(self) -> list[GroupRecord]:
        rows = await group_repository.list_groups()
        return [self._to_record(row) for row in rows]

    def _to_record(self, row: "GroupConsole") -> GroupRecord:
        raw_disabled_plugins = getattr(row, "disabled_plugins", "[]")
        disabled_plugins = [
            module
            for module in decode_disabled_plugins(raw_disabled_plugins)
            if not get_plugin_protection_reason(module)
        ]
        return GroupRecord(
            group_id=row.group_id,
            group_name=row.group_name,
            bot_status=row.bot_status,
            disabled_plugins=disabled_plugins,
        )


group_service = GroupService()
