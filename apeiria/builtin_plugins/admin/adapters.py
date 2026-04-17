"""Owner-facing adapter inspection command."""

from __future__ import annotations

from typing import TYPE_CHECKING

import nonebot
from arclet.alconna import CommandMeta
from nonebot.adapters import Event  # noqa: TC002
from nonebot_plugin_alconna import Alconna, on_alconna

from apeiria.app.plugins import config_query_service
from apeiria.shared.i18n import t

from .presenter import render_list_block
from .utils import ensure_owner_message

if TYPE_CHECKING:
    from apeiria.app.plugins.registration_service import AdapterConfigStatus

_adapters = on_alconna(
    Alconna("adapters", meta=CommandMeta(description=t("admin.command.adapters"))),
    use_cmd_start=True,
    priority=5,
    block=True,
)


@_adapters.handle()
async def handle_adapters(event: Event) -> None:
    owner_error = ensure_owner_message(event)
    if owner_error:
        await _adapters.finish(owner_error)

    state = config_query_service.get_adapter_config()
    loaded_runtime = sorted(nonebot.get_adapters().keys())
    lines = [_format_adapter_line(item) for item in state.modules]
    loaded_runtime_names = (
        ", ".join(loaded_runtime) if loaded_runtime else t("admin.common.none")
    )
    await _adapters.finish(
        render_list_block(
            t("admin.adapters.title"),
            lines,
            summary=t(
                "admin.adapters.summary",
                configured=len(state.modules),
                loaded=len(loaded_runtime),
            ),
            empty_message=t("admin.adapters.empty"),
            footer=t("admin.adapters.footer", names=loaded_runtime_names),
        )
    )


def _format_adapter_line(item: AdapterConfigStatus) -> str:
    load_status = (
        t("admin.adapters.loaded") if item.is_loaded else t("admin.adapters.not_loaded")
    )
    import_status = (
        t("admin.adapters.importable")
        if item.is_importable
        else t("admin.adapters.not_importable")
    )
    return f"- {item.name} | {load_status} | {import_status}"
