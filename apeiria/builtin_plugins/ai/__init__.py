"""AI plugin skeleton — NoneBot-facing shell for the AI domain."""

from nonebot import require
from nonebot.adapters import Bot, Event
from nonebot.permission import SUPERUSER
from nonebot.plugin import PluginMetadata, inherit_supported_adapters
from nonebot.plugin.on import on_command, on_message

from apeiria.app.ai import ai_service
from apeiria.app.ai.config import AIPluginConfig
from apeiria.app.ai.runtime import ai_runtime_service
from apeiria.shared.plugin_metadata import (
    ConfigExtra,
    PluginExtraData,
    PluginType,
    RegisterConfig,
    UiExtra,
)

require("nonebot_plugin_alconna")
require("nonebot_plugin_orm")

__plugin_meta__ = PluginMetadata(
    name="AI Plugin",
    description="Apeiria AI plugin rewrite skeleton",
    homepage="https://github.com/Cccc-owo/apeiria_bot",
    usage="Use /ai-status to verify that the AI plugin skeleton is loaded.",
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
            ]
        ),
        commands=["ai-status"],
        required_plugins=["nonebot_plugin_alconna", "nonebot_plugin_orm"],
    ).to_dict(),
)

ai_status = on_command("ai-status", permission=SUPERUSER, block=True)
ai_message = on_message(priority=50, block=False)


@ai_status.handle()
async def handle_ai_status() -> None:
    """Return the current bootstrap status of the AI domain."""
    status = ai_service.get_status()
    await ai_status.finish(f"{status.phase}: {status.summary}")


@ai_message.handle()
async def handle_ai_message(bot: Bot, event: Event) -> None:
    """Minimal working AI reply loop."""
    reply = await ai_runtime_service.handle_message(bot, event)
    if reply:
        await bot.send(event, reply)
