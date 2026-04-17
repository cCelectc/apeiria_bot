"""Owner-facing driver inspection command."""

from __future__ import annotations

from typing import TYPE_CHECKING

import nonebot
from arclet.alconna import CommandMeta
from nonebot.adapters import Event  # noqa: TC002
from nonebot_plugin_alconna import Alconna, on_alconna

from apeiria.app.plugins import config_query_service
from apeiria.shared.i18n import t

from .presenter import render_block, render_list_block
from .utils import ensure_owner_message

if TYPE_CHECKING:
    from apeiria.app.plugins.registration_service import DriverConfigStatus

_drivers = on_alconna(
    Alconna("drivers", meta=CommandMeta(description=t("admin.command.drivers"))),
    use_cmd_start=True,
    priority=5,
    block=True,
)


@_drivers.handle()
async def handle_drivers(event: Event) -> None:
    owner_error = ensure_owner_message(event)
    if owner_error:
        await _drivers.finish(owner_error)

    driver = nonebot.get_driver()
    state = config_query_service.get_driver_config()
    lines = [_format_driver_line(item) for item in state.builtin]

    await _drivers.finish(
        "\n\n".join(
            [
                render_block(
                    t("admin.drivers.runtime_title"),
                    [
                        (t("admin.drivers.field_class"), driver.__class__.__name__),
                        (t("admin.drivers.field_module"), driver.__class__.__module__),
                    ],
                ),
                render_list_block(
                    t("admin.drivers.configured_title"),
                    lines,
                    summary=t("admin.drivers.summary", count=len(state.builtin)),
                    empty_message=t("admin.drivers.empty"),
                ),
            ]
        )
    )


def _format_driver_line(item: DriverConfigStatus) -> str:
    status = (
        t("admin.drivers.active") if item.is_active else t("admin.drivers.inactive")
    )
    return f"- {item.name} | {status}"
