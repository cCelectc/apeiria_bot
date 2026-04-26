"""AI plugin shell — wires the AI capability into NoneBot's lifecycle.

This module is intentionally thin. It:

- Declares AI's PluginMetadata (config, commands, UI metadata)
- Subscribes AI's message pipeline to NoneBot's `on_message` event
- Publishes AI's HTTP routes into the Web UI host via the plugin-router
  registry — so disabling this plugin also removes `/api/ai/*`

Stable AI capabilities live under :mod:`apeiria.ai`, orchestration lives
under :mod:`apeiria.app.ai`, and HTTP route ownership lives under
:mod:`apeiria.webui.routes.ai`.
"""

from nonebot import require
from nonebot.adapters import Bot, Event
from nonebot.permission import SUPERUSER
from nonebot.plugin import PluginMetadata, inherit_supported_adapters
from nonebot.plugin.on import on_command, on_message

from apeiria.ai import ai_service
from apeiria.ai.config import AIPluginConfig
from apeiria.app.ai.pipeline import AITraceContext, ai_runtime_service
from apeiria.plugins.metadata.api import (
    ConfigExtra,
    PluginExtraData,
    PluginType,
    RegisterConfig,
    UiExtra,
)
from apeiria.runtime.entries import build_ai_trace_entry
from apeiria.webui.plugin_routers import register_plugin_router
from apeiria.webui.routes.ai import router as ai_webui_router

require("nonebot_plugin_alconna")

__plugin_meta__ = PluginMetadata(
    name="AI Plugin",
    description="Apeiria AI runtime and admin surfaces",
    homepage="https://github.com/Cccc-owo/apeiria_bot",
    usage="Use /ai-status to inspect the loaded AI runtime.",
    type="application",
    config=AIPluginConfig,
    supported_adapters=inherit_supported_adapters("nonebot_plugin_alconna"),
    extra=PluginExtraData(
        author="apeiria",
        version="0.1.0",
        plugin_type=PluginType.NORMAL,
        admin_level=0,
        ui=UiExtra(order=0),
        config=ConfigExtra(
            fields=[
                RegisterConfig(
                    key="allow_group_initiative",
                    default=False,
                    help=(
                        "Allow AI to consider non-mention group messages as "
                        "initiative candidates."
                    ),
                    type=bool,
                ),
                RegisterConfig(
                    key="persist_raw_event_payloads",
                    default=False,
                    help=(
                        "Persist reduced raw event payloads for AI debugging "
                        "and workbench inspection."
                    ),
                    type=bool,
                ),
                RegisterConfig(
                    key="tool_execution_timeout_seconds",
                    default=8.0,
                    help="Maximum seconds allowed for one AI tool execution.",
                    type=float,
                ),
                RegisterConfig(
                    key="cleanup_interval_minutes",
                    default=30,
                    help=(
                        "Minimum interval between automatic AI retention cleanup runs."
                    ),
                    type=int,
                ),
                RegisterConfig(
                    key="conversation_retention_days",
                    default=30,
                    help="Retention window for persisted AI chat messages.",
                    type=int,
                ),
                RegisterConfig(
                    key="raw_event_retention_days",
                    default=7,
                    help=("Retention window for reduced persisted raw event payloads."),
                    type=int,
                ),
                RegisterConfig(
                    key="tool_execution_retention_days",
                    default=30,
                    help="Retention window for AI tool execution audit rows.",
                    type=int,
                ),
                RegisterConfig(
                    key="ignored_memory_retention_days",
                    default=30,
                    help="Retention window for ignored AI memory rows.",
                    type=int,
                ),
            ]
        ),
        commands=["ai-status"],
        required_plugins=["nonebot_plugin_alconna"],
    ).to_dict(),
)

ai_status = on_command("ai-status", permission=SUPERUSER, block=True)
ai_message = on_message(priority=50, block=False)

# Publish AI's HTTP router into the Web UI host. Registration happens at
# plugin import time — when this plugin is disabled, the registration never
# runs and `/api/ai/*` stays off.
register_plugin_router("/ai", ai_webui_router, tags=("ai",))


@ai_status.handle()
async def handle_ai_status() -> None:
    """Return the current bootstrap status of the AI domain."""
    status = ai_service.get_status()
    await ai_status.finish(f"{status.phase}: {status.summary}")


@ai_message.handle()
async def handle_ai_message(bot: Bot, event: Event) -> None:
    """Run the AI reply loop for one incoming event."""
    entry = build_ai_trace_entry("message", event=event)
    reply = await ai_runtime_service.handle_message(
        bot,
        event,
        trace=AITraceContext(
            kind=entry.kind.value,
            trigger=entry.trigger.value,
        ),
    )
    if reply:
        await bot.send(event, reply)
