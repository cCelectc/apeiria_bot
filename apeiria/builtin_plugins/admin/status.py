"""Owner-facing runtime status command."""

from __future__ import annotations

import time

import nonebot
from arclet.alconna import CommandMeta
from nonebot.adapters import Event  # noqa: TC002
from nonebot_plugin_alconna import Alconna, on_alconna

from apeiria.i18n import t
from apeiria.utils.time_format import format_duration

from .presenter import render_block
from .utils import ensure_owner_message

_start_time = time.monotonic()

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

    uptime = int(time.monotonic() - _start_time)
    plugins_count = len(nonebot.get_loaded_plugins())

    adapters = ", ".join(
        type(a).__name__ for a in nonebot.get_driver()._adapters.values()
    ) or t("admin.status.adapters_none")

    await _status.finish(
        render_block(
            t("admin.status.title"),
            [
                (
                    t("admin.status.field_runtime"),
                    format_duration(uptime),
                ),
                (t("admin.status.field_status"), t("admin.status.running")),
                (t("admin.status.field_plugins"), plugins_count),
                (t("admin.status.field_adapters"), adapters),
            ],
        )
    )
