from __future__ import annotations

from nonebot.adapters import Bot, Event  # noqa: TC002
from nonebot.log import logger
from nonebot.matcher import Matcher  # noqa: TC002
from nonebot.plugin import PluginMetadata
from nonebot.plugin.on import on_message
from nonebot.rule import Rule

from apeiria.plugin.metadata.api import (
    ConfigExtra,
    HelpExtra,
    PluginExtraData,
    PluginType,
    RegisterConfig,
    UiExtra,
)

from .config import RepeaterConfig, get_plugin_config
from .service import RepeaterService, hash_message

__plugin_meta__ = PluginMetadata(
    name="群聊复读机",
    description="在配置群里按连续复读氛围概率原样复读一次。",
    homepage="https://github.com/Cccc-owo/apeiria_bot",
    usage="配置群白名单或黑名单后，群友连续发送相同内容时概率复读。",
    type="application",
    config=RepeaterConfig,
    supported_adapters=None,
    extra=PluginExtraData(
        author="apeiria",
        version="0.1.0",
        plugin_type=PluginType.NORMAL,
        help=HelpExtra(
            category="基础功能",
            introduction="在指定群聊中跟随群友复读文本、表情和稳定图片消息。",
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
                    help="允许生效的群，格式为 platform:group_id。为空时所有群生效。",
                    type=list,
                    item_type=str,
                    label="群白名单",
                    order=40,
                ),
                RegisterConfig(
                    key="blocklist",
                    default=[],
                    help="禁止生效的群，格式为 platform:group_id，冲突时优先。",
                    type=list,
                    item_type=str,
                    label="群黑名单",
                    order=50,
                ),
            ]
        ),
    ).to_dict(),
)

_service = RepeaterService()


async def _is_configured_group_message(bot: Bot, event: Event) -> bool:
    group_id = _group_id_from_event(event)
    if group_id is None:
        return False
    config = get_plugin_config()
    platform = _platform_from_bot(bot)
    scope = f"{platform}:{group_id}"
    if config.blocklist and scope in config.blocklist:
        return False
    return not (config.allowlist and scope not in config.allowlist)


_repeater = on_message(
    Rule(_is_configured_group_message),
    priority=9,
    block=False,
)


@_repeater.handle()
async def handle_repeater(bot: Bot, event: Event, matcher: Matcher) -> None:
    config = get_plugin_config()
    group_id = _group_id_from_event(event)
    if group_id is None:
        return
    platform = _platform_from_bot(bot)
    scope = f"{platform}:{group_id}"
    user_id = _user_id_from_event(event)
    if user_id is None:
        return

    bot_id = _bot_id(bot)
    if bot_id is not None and user_id == bot_id:
        return

    message = _message_from_event(event)
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
        logger.debug("群聊复读机发送失败")


def _platform_from_bot(bot: Bot) -> str | None:
    platform = str(getattr(bot, "type", "") or "").strip().lower()
    return platform or None


def _group_id_from_event(event: Event) -> str | None:
    try:
        gid = getattr(event, "group_id", None)
    except Exception:  # noqa: BLE001
        return None
    else:
        if gid is not None:
            return str(gid)
        return None


def _user_id_from_event(event: Event) -> str | None:
    try:
        return str(event.get_user_id())
    except Exception:  # noqa: BLE001
        return None


def _bot_id(bot: Bot) -> str | None:
    bot_id = str(getattr(bot, "self_id", "") or "").strip()
    return bot_id or None


def _message_from_event(event: Event) -> object:
    try:
        return event.get_message()
    except Exception:  # noqa: BLE001
        return getattr(event, "message", "")
