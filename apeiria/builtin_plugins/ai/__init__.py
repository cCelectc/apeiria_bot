"""AI plugin skeleton — NoneBot-facing shell for the AI domain."""

from nonebot import require
from nonebot.permission import SUPERUSER
from nonebot.plugin import PluginMetadata, inherit_supported_adapters
from nonebot.plugin.on import on_command

from apeiria.app.ai import ai_service
from apeiria.shared.plugin_metadata import PluginExtraData, PluginType, UiExtra

require("nonebot_plugin_alconna")
require("nonebot_plugin_orm")

__plugin_meta__ = PluginMetadata(
    name="AI Plugin",
    description="Apeiria AI plugin rewrite skeleton",
    homepage="https://github.com/Cccc-owo/apeiria_bot",
    usage="Use /ai-status to verify that the AI plugin skeleton is loaded.",
    type="application",
    supported_adapters=inherit_supported_adapters("nonebot_plugin_alconna"),
    extra=PluginExtraData(
        author="apeiria",
        version="0.1.0",
        plugin_type=PluginType.HIDDEN,
        admin_level=0,
        ui=UiExtra(order=0, hidden=True),
        commands=["ai-status"],
        required_plugins=["nonebot_plugin_alconna", "nonebot_plugin_orm"],
    ).to_dict(),
)

ai_status = on_command("ai-status", permission=SUPERUSER, block=True)


@ai_status.handle()
async def handle_ai_status() -> None:
    """Return the current bootstrap status of the AI domain."""
    status = ai_service.get_status()
    await ai_status.finish(f"{status.phase}: {status.summary}")
