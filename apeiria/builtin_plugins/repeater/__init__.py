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

from apeiria.plugin.metadata.api import (
    ConfigExtra,
    HelpExtra,
    PluginExtraData,
    PluginType,
    RegisterConfig,
    UiExtra,
)
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
    extra=PluginExtraData(
        author="apeiria",
        version="0.2.0",
        plugin_type=PluginType.NORMAL,
        help=HelpExtra(
            category="基础功能",
            introduction="在指定群聊中跟随群友复读文本、表情和稳定图片消息。"
            " 白/黑名单使用 scope:group_id 格式（如 QQClient:群号）。",
        ),
        ui=UiExtra(label="群聊复读机", order=18),
        config=ConfigExtra(
            fields=[
                RegisterConfig(
                    key="probability",
                    default=0.3,
                    help="达到复读阈值后的复读概率。",
                    type=float,
                    label="复读概率",
                    order=10,
                ),
                RegisterConfig(
                    key="cooldown_seconds",
                    default=60,
                    help="复读一次的冷却时间（秒）。",
                    type=int,
                    label="冷却时间",
                    order=20,
                ),
                RegisterConfig(
                    key="repeat_threshold",
                    default=2,
                    help="连续不同用户发送相同内容达到该次数后触发复读。",
                    type=int,
                    label="触发阈值",
                    order=30,
                ),
                RegisterConfig(
                    key="allowlist",
                    default=[],
                    help="允许生效的群，格式为 scope:group_id。为空时所有群生效。",
                    type=list,
                    item_type=str,
                    label="群白名单",
                    order=40,
                ),
                RegisterConfig(
                    key="blocklist",
                    default=[],
                    help="禁止生效的群，格式为 scope:group_id，冲突时优先。",
                    type=list,
                    item_type=str,
                    label="群黑名单",
                    order=50,
                ),
            ]
        ),
        required_plugins=["nonebot_plugin_uninfo"],
    ).to_dict(),
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
