from __future__ import annotations

import time

import nonebot
from arclet.alconna import CommandMeta
from nonebot.adapters import Event  # noqa: TC002
from nonebot_plugin_alconna import Alconna, on_alconna

from .presenter import render_block
from .utils import ensure_owner_message

_start_time = time.monotonic()

_status = on_alconna(
    Alconna("status", meta=CommandMeta(description="查看运行状态")),
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
    adapters = (
        ", ".join(type(a).__name__ for a in nonebot.get_driver()._adapters.values())
        or "无"
    )

    await _status.finish(
        render_block(
            "运行状态",
            [
                ("运行时间", f"{uptime}s"),
                ("状态", "运行中"),
                ("已加载插件", plugins_count),
                ("适配器", adapters),
            ],
        )
    )
