"""Owner-facing restart command."""

from __future__ import annotations

from arclet.alconna import CommandMeta
from nonebot.adapters import Event  # noqa: TC002
from nonebot_plugin_alconna import Alconna, on_alconna

from apeiria.environment.dashboard import dashboard_service
from apeiria.i18n import t

from .utils import ensure_owner_message

_restart = on_alconna(
    Alconna("restart", meta=CommandMeta(description=t("admin.command.restart"))),
    use_cmd_start=True,
    priority=5,
    block=True,
)


@_restart.handle()
async def handle_restart(event: Event) -> None:
    owner_error = ensure_owner_message(event)
    if owner_error:
        await _restart.finish(owner_error)

    dashboard_service.schedule_restart()
    await _restart.finish(t("admin.restart.scheduled"))
