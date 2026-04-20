"""Owner-facing admin overview command."""

from __future__ import annotations

from arclet.alconna import CommandMeta
from nonebot.adapters import Event  # noqa: TC002
from nonebot_plugin_alconna import Alconna, on_alconna

from apeiria.environment.dashboard import dashboard_service
from apeiria.i18n import t
from apeiria.utils.time_format import format_duration

from .presenter import render_block, render_list_block
from .utils import ensure_owner_message

_admin = on_alconna(
    Alconna("admin", meta=CommandMeta(description=t("admin.command.admin"))),
    use_cmd_start=True,
    priority=5,
    block=True,
)


@_admin.handle()
async def handle_admin(event: Event) -> None:
    owner_error = ensure_owner_message(event)
    if owner_error:
        await _admin.finish(owner_error)

    snapshot = await dashboard_service.get_status_snapshot()
    adapters = (
        ", ".join(snapshot.adapters)
        if snapshot.adapters
        else t("admin.status.adapters_none")
    )
    await _admin.finish(
        "\n\n".join(
            [
                render_block(
                    t("admin.overview.title"),
                    [
                        (
                            t("admin.status.field_runtime"),
                            format_duration(int(snapshot.uptime)),
                        ),
                        (t("admin.status.field_plugins"), snapshot.plugins_count),
                        (
                            t("admin.status.field_disabled_plugins"),
                            snapshot.disabled_plugins_count,
                        ),
                        (t("admin.status.field_groups"), snapshot.groups_count),
                        (
                            t("admin.status.field_access_rules"),
                            snapshot.access_rules_count,
                        ),
                        (t("admin.status.field_adapters"), adapters),
                    ],
                    summary=t("admin.overview.summary"),
                ),
                render_list_block(
                    t("admin.overview.commands_title"),
                    [
                        t("admin.overview.command_status"),
                        t("admin.overview.command_plugins"),
                        t("admin.overview.command_plugin"),
                        t("admin.overview.command_config"),
                        t("admin.overview.command_access"),
                        t("admin.overview.command_tasks"),
                        t("admin.overview.command_restart"),
                    ],
                ),
            ]
        )
    )
