from __future__ import annotations

from contextlib import suppress

from nonebot import require
from nonebot.adapters import Bot, Event  # noqa: TC002
from nonebot.log import logger
from nonebot.matcher import Matcher  # noqa: TC002
from nonebot.plugin import PluginMetadata, inherit_supported_adapters
from nonebot.plugin.on import on_message
from nonebot.rule import Rule

require("nonebot_plugin_uninfo")
from nonebot_plugin_uninfo import SceneType, Uninfo

from apeiria.utils.session import scoped_group_id

from .config import RepeaterConfig, get_plugin_config
from .service import RepeaterService, hash_message

__plugin_meta__ = PluginMetadata(
    name="群聊复读机",
    description="在配置群里按连续复读氛围概率原样复读一次。",
    homepage="https://github.com/Cccc-owo/apeiria_bot",
    usage="配置群白名单或黑名单后，群友连续发送相同内容时概率复读。",
    type="application",
    config=RepeaterConfig,
    supported_adapters=inherit_supported_adapters("nonebot_plugin_uninfo"),
)

_service = RepeaterService()


async def _is_configured_group_message(
    session: Uninfo,
) -> bool:
    scene_type = getattr(session.scene, "type", None)
    if scene_type is not None and scene_type != SceneType.GROUP:
        return False
    config = get_plugin_config()
    scope = scoped_group_id(session)
    if config.blocklist and scope in config.blocklist:
        return False
    return not (config.allowlist and scope not in config.allowlist)


_repeater = on_message(
    Rule(_is_configured_group_message),
    priority=9,
    block=False,
)


@_repeater.handle()
async def handle_repeater(
    bot: Bot,
    event: Event,
    matcher: Matcher,
    session: Uninfo,
) -> None:
    config = get_plugin_config()
    scope = scoped_group_id(session)
    user_id = session.user.id

    bot_id = str(getattr(bot, "self_id", "")).strip()
    if bot_id and user_id == bot_id:
        return

    message = None
    with suppress(Exception):
        message = event.get_message()
    if message is None:
        return

    content_hash = hash_message(message)
    result = _service.evaluate(
        scope,
        content_hash,
        message,
        user_id,
        config=config,
    )
    if result is None:
        return

    try:
        await matcher.send(result)
    except Exception:  # noqa: BLE001
        logger.warning("群聊复读机发送失败")


__all__ = ["_repeater", "handle_repeater"]
