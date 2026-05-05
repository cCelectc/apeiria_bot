"""Owner-facing runtime status command."""

from __future__ import annotations

from arclet.alconna import CommandMeta
from nonebot.adapters import Event  # noqa: TC002
from nonebot_plugin_alconna import Alconna, on_alconna

from apeiria.i18n import t
from apeiria.utils.time_format import format_duration

from .presenter import render_block
from .utils import ensure_owner_message, get_runtime_control_plane

_status = on_alconna(
    Alconna("status", meta=CommandMeta(description=t("admin.command.status"))),
    use_cmd_start=True,
    priority=5,
    block=True,
)


@_status.handle()
async def handle_status(event: Event) -> None:
    owner_error = ensure_owner_message(event)
    if owner_error:
        await _status.finish(owner_error)

    control_plane = get_runtime_control_plane()
    if control_plane is None:
        await _status.finish(t("admin.runtime_control_plane_unavailable"))

    snapshot = await control_plane.get_dashboard_status()
    adapters = (
        ", ".join(snapshot.adapters)
        if snapshot.adapters
        else t("admin.status.adapters_none")
    )

    await _status.finish(
        render_block(
            t("admin.status.title"),
            [
                (
                    t("admin.status.field_runtime"),
                    format_duration(int(snapshot.uptime)),
                ),
                (t("admin.status.field_status"), t("admin.status.running")),
                (t("admin.status.field_plugins"), snapshot.plugins_count),
                (
                    t("admin.status.field_disabled_plugins"),
                    snapshot.disabled_plugins_count,
                ),
                (t("admin.status.field_groups"), snapshot.groups_count),
                (
                    t("admin.status.field_disabled_groups"),
                    snapshot.disabled_groups_count,
                ),
                (t("admin.status.field_access_rules"), snapshot.access_rules_count),
                (t("admin.status.field_adapters"), adapters),
            ],
        )
    )
