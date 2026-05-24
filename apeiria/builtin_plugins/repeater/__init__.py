"""Repeater built-in plugin."""

from __future__ import annotations

from typing import Any, cast

from nonebot.adapters import Bot, Event  # noqa: TC002
from nonebot.log import logger
from nonebot.matcher import Matcher  # noqa: TC002
from nonebot.plugin import PluginMetadata
from nonebot.plugin.on import on_message
from nonebot.rule import Rule

from apeiria.bot.event_context import group_id_from_event
from apeiria.plugins.metadata.api import (
    ConfigExtra,
    HelpExtra,
    PluginExtraData,
    PluginType,
    RegisterConfig,
    UiExtra,
)

from .config import (
    DEFAULT_BASE_PROBABILITY,
    DEFAULT_GROUP_MODE,
    DEFAULT_MAX_PROBABILITY,
    DEFAULT_PLATFORMS,
    DEFAULT_REPEAT_THRESHOLD,
    DEFAULT_SATURATION_EXTRA,
    RepeaterConfig,
    get_repeater_config,
)
from .service import (
    RepeaterEvent,
    default_repeater_service,
)

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
                    key="repeat_threshold",
                    default=DEFAULT_REPEAT_THRESHOLD,
                    help="连续不同用户发送相同内容达到该次数后开始抽取复读概率。",
                    type=int,
                    label="触发阈值",
                    order=10,
                ),
                RegisterConfig(
                    key="platforms",
                    default=list(DEFAULT_PLATFORMS),
                    help="启用的平台标识列表，例如 qq。",
                    type=list,
                    item_type=str,
                    label="启用平台",
                    order=20,
                ),
                RegisterConfig(
                    key="group_mode",
                    default=DEFAULT_GROUP_MODE,
                    help=(
                        "群范围模式：allowlist 仅白名单生效，"
                        "blocklist 默认生效但排除黑名单。"
                    ),
                    type=str,
                    choices=["allowlist", "blocklist"],
                    choice_labels={
                        "allowlist": "白名单",
                        "blocklist": "黑名单",
                    },
                    label="群范围模式",
                    order=30,
                ),
                RegisterConfig(
                    key="allow_groups",
                    default=[],
                    help="允许生效的群，格式为 platform:group_id。",
                    type=list,
                    item_type=str,
                    label="群白名单",
                    order=40,
                ),
                RegisterConfig(
                    key="deny_groups",
                    default=[],
                    help="禁止生效的群，格式为 platform:group_id，冲突时优先。",
                    type=list,
                    item_type=str,
                    label="群黑名单",
                    order=50,
                ),
                RegisterConfig(
                    key="base_probability",
                    default=DEFAULT_BASE_PROBABILITY,
                    help="刚达到阈值时的复读概率。",
                    type=float,
                    label="基础概率",
                    order=60,
                ),
                RegisterConfig(
                    key="max_probability",
                    default=DEFAULT_MAX_PROBABILITY,
                    help="连续复读人数增加后概率的上限。",
                    type=float,
                    label="最大概率",
                    order=70,
                ),
                RegisterConfig(
                    key="saturation_extra",
                    default=DEFAULT_SATURATION_EXTRA,
                    help="从基础概率爬升到概率上限所需的额外重复次数。",
                    type=int,
                    label="饱和次数",
                    order=80,
                ),
                RegisterConfig(
                    key="debug",
                    default=False,
                    help="启用后记录跳过原因和调试日志。",
                    type=bool,
                    label="调试日志",
                    order=90,
                ),
            ]
        ),
    ).to_dict(),
)


async def _is_configured_group_message(bot: Bot, event: Event) -> bool:
    repeater_event = build_repeater_event(bot, event)
    config = get_repeater_config()
    group_scope = repeater_event.group_scope
    if not config.active:
        if config.debug:
            logger.debug("Group repeater inactive: {}", config.errors)
        return False
    if repeater_event.platform not in config.platforms:
        if config.debug:
            logger.debug(
                "Group repeater skipped disabled platform {}",
                repeater_event.platform,
            )
        return False
    if group_scope is None:
        if config.debug:
            logger.debug("Group repeater skipped non-group message")
        return False
    if not config.is_group_allowed(group_scope):
        if config.debug:
            logger.debug("Group repeater skipped disallowed group {}", group_scope)
        return False
    return True


_repeater = on_message(
    Rule(_is_configured_group_message),
    priority=9,
    block=False,
)


@_repeater.handle()
async def handle_repeater(bot: Bot, event: Event, matcher: Matcher) -> None:
    config = get_repeater_config()
    repeater_event = build_repeater_event(bot, event)
    decision = default_repeater_service.evaluate(
        repeater_event,
        config=config,
    )
    if not decision.should_send or decision.message is None:
        return

    if decision.group_scope is not None:
        default_repeater_service.mark_triggered(decision.group_scope)
    try:
        await matcher.send(cast("Any", decision.message))
    except Exception as exc:  # noqa: BLE001
        logger.debug("Group repeater send failed: {}", exc)


def build_repeater_event(bot: Bot, event: Event) -> RepeaterEvent:
    return RepeaterEvent(
        platform=_platform_from_bot(bot),
        group_id=group_id_from_event(event),
        user_id=_user_id_from_event(event),
        bot_id=_bot_id(bot),
        message=_message_from_event(event),
    )


def _platform_from_bot(bot: Bot) -> str | None:
    platform = str(getattr(bot, "type", "") or "").strip().lower()
    return platform or None


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


__all__ = ["_repeater", "build_repeater_event", "handle_repeater"]
