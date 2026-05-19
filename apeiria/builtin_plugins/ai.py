"""AI plugin shell — wires the AI capability into NoneBot's lifecycle.

This module is intentionally thin. It:

- Declares AI's PluginMetadata (config, commands, UI metadata)
- Subscribes AI's message pipeline to NoneBot's `on_message` event

Stable AI capabilities live under :mod:`apeiria.ai`, orchestration lives
under :mod:`apeiria.app.ai`, and HTTP route ownership lives under the Web UI
control plane so configuration remains editable while runtime execution is off.
"""

from nonebot import get_driver, require
from nonebot.adapters import Bot, Event
from nonebot.permission import SUPERUSER
from nonebot.plugin import PluginMetadata, inherit_supported_adapters
from nonebot.plugin.on import on_command, on_message

from apeiria.app.ai import ai_application
from apeiria.app.ai.runtime.contracts import RuntimeTraceContext
from apeiria.plugins.metadata.api import (
    PluginExtraData,
    PluginType,
    UiExtra,
)
from apeiria.runtime.entries import build_ai_trace_entry

require("nonebot_plugin_alconna")

__plugin_meta__ = PluginMetadata(
    name="AI",
    description="System-level AI behavior switch and message runtime.",
    homepage="https://github.com/Cccc-owo/apeiria_bot",
    usage="Use /ai-status to view the current AI runtime state.",
    type="application",
    supported_adapters=inherit_supported_adapters("nonebot_plugin_alconna"),
    extra=PluginExtraData(
        author="apeiria",
        version="0.1.0",
        plugin_type=PluginType.NORMAL,
        ui=UiExtra(label="AI", order=0),
        commands=["ai-status"],
        required_plugins=["nonebot_plugin_alconna"],
    ).to_dict(),
)

ai_status = on_command("ai-status", permission=SUPERUSER, block=True)
ai_message = on_message(priority=50, block=False)


async def _run_ai_lifecycle_startup() -> None:
    """Prepare AI startup support after configured user plugins are loaded."""

    await ai_application.lifecycle.startup()


get_driver().on_startup(_run_ai_lifecycle_startup)


@ai_status.handle()
async def handle_ai_status() -> None:
    """Return the current bootstrap status of the AI domain."""
    status = await ai_application.diagnostics.get_runtime_status()
    await ai_status.finish(f"{status.phase}: {status.summary}")


@ai_message.handle()
async def handle_ai_message(bot: Bot, event: Event) -> None:
    """Run the AI reply loop for one incoming event."""
    entry = build_ai_trace_entry("message", event=event)
    reply = await ai_application.runtime.handle_message(
        bot,
        event,
        trace=RuntimeTraceContext(
            kind=entry.kind.value,
            trigger=entry.trigger.value,
        ),
    )
    if reply:
        await bot.send(event, reply)
