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

from apeiria.ai.config import AIPluginConfig
from apeiria.app.ai import ai_application
from apeiria.app.ai.runtime.contracts import RuntimeTraceContext
from apeiria.plugins.metadata.api import (
    ConfigExtra,
    PluginExtraData,
    PluginType,
    RegisterConfig,
    UiExtra,
)
from apeiria.runtime.entries import build_ai_trace_entry

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
                    key="ambient_merge_window_ms",
                    default=1500,
                    help="Milliseconds to merge short ambient group-message bursts.",
                    type=int,
                ),
                RegisterConfig(
                    key="max_pending_messages",
                    default=12,
                    help="Maximum pending ambient messages retained for one AI turn.",
                    type=int,
                ),
                RegisterConfig(
                    key="group_reply_cooldown_seconds",
                    default=180,
                    help="Cooldown for default ambient group-chat AI replies.",
                    type=int,
                ),
                RegisterConfig(
                    key="max_consecutive_ambient_replies",
                    default=1,
                    help="Maximum consecutive AI replies to ambient group messages.",
                    type=int,
                ),
                RegisterConfig(
                    key="direct_bypass_ambient_budget",
                    default=True,
                    help=(
                        "Let direct mentions, private messages, and future tasks "
                        "bypass ambient initiative budget."
                    ),
                    type=bool,
                ),
                RegisterConfig(
                    key="duplicate_event_ttl_seconds",
                    default=30,
                    help="Seconds to keep local duplicate event protection entries.",
                    type=int,
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
                    key="suppressed_memory_retention_days",
                    default=30,
                    help="Retention window for suppressed AI memory rows.",
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
