"""Contact-owner built-in plugin."""

from __future__ import annotations

from nonebot.adapters import Bot, Event  # noqa: TC002
from nonebot.matcher import Matcher  # noqa: TC002
from nonebot.plugin import PluginMetadata
from nonebot.plugin.on import on_message
from nonebot.rule import Rule

from apeiria.plugins.metadata.api import (
    ConfigExtra,
    HelpExtra,
    PluginExtraData,
    PluginType,
    RegisterConfig,
    UiExtra,
)

from .config import (
    DEFAULT_CONTACT_PREFIX,
    DEFAULT_DELIVERY_FAILED_REPLY,
    DEFAULT_EMPTY_MESSAGE_REPLY,
    DEFAULT_INVALID_OWNER_TARGET_REPLY,
    DEFAULT_OWNER_UNCONFIGURED_REPLY,
    DEFAULT_SUCCESS_REPLY,
    DEFAULT_TOO_SHORT_REPLY,
    DEFAULT_UNSUPPORTED_PLATFORM_REPLY,
    ContactOwnerConfig,
    get_contact_owner_config,
)
from .service import handle_contact_owner_event

__plugin_meta__ = PluginMetadata(
    name="联系主人",
    description="允许用户通过配置前缀给主人留下留言。",
    homepage="https://github.com/Cccc-owo/apeiria_bot",
    usage="发送「联系主人 留言内容」给主人留言。",
    type="application",
    config=ContactOwnerConfig,
    supported_adapters=None,
    extra=PluginExtraData(
        author="apeiria",
        version="0.1.0",
        plugin_type=PluginType.NORMAL,
        help=HelpExtra(
            category="基础功能",
            introduction="通过配置前缀把用户留言转发给指定主人。",
        ),
        ui=UiExtra(label="联系主人", order=17),
        config=ConfigExtra(
            fields=[
                RegisterConfig(
                    key="contact_prefix",
                    default=DEFAULT_CONTACT_PREFIX,
                    help="触发联系主人的文本前缀。",
                    type=str,
                    label="联系前缀",
                    order=10,
                ),
                RegisterConfig(
                    key="owner_target",
                    default="",
                    help="主人目标，格式为 scope:id。第一版支持 qq:QQ号。",
                    type=str,
                    label="主人目标",
                    order=20,
                ),
                RegisterConfig(
                    key="minimum_message_length",
                    default=0,
                    help="留言正文必须超过该字符数才会转发。",
                    type=int,
                    label="最小留言长度",
                    order=30,
                ),
                RegisterConfig(
                    key="success_reply",
                    default=DEFAULT_SUCCESS_REPLY,
                    help="留言转发成功时回复给用户的文本。",
                    type=str,
                    label="成功回应",
                    order=40,
                ),
                RegisterConfig(
                    key="empty_message_reply",
                    default=DEFAULT_EMPTY_MESSAGE_REPLY,
                    help="留言为空时回复给用户的文本。",
                    type=str,
                    label="空留言提示",
                    order=50,
                ),
                RegisterConfig(
                    key="too_short_reply",
                    default=DEFAULT_TOO_SHORT_REPLY,
                    help="留言不超过最小长度时回复给用户的文本。",
                    type=str,
                    label="留言过短提示",
                    order=60,
                ),
                RegisterConfig(
                    key="owner_unconfigured_reply",
                    default=DEFAULT_OWNER_UNCONFIGURED_REPLY,
                    help="未配置主人目标时回复给用户的文本。",
                    type=str,
                    label="未配置提示",
                    order=70,
                ),
                RegisterConfig(
                    key="invalid_owner_target_reply",
                    default=DEFAULT_INVALID_OWNER_TARGET_REPLY,
                    help="主人目标格式错误时回复给用户的文本。",
                    type=str,
                    label="目标格式错误提示",
                    order=80,
                ),
                RegisterConfig(
                    key="unsupported_platform_reply",
                    default=DEFAULT_UNSUPPORTED_PLATFORM_REPLY,
                    help="当前平台或目标 scope 不支持时回复给用户的文本。",
                    type=str,
                    label="平台不支持提示",
                    order=90,
                ),
                RegisterConfig(
                    key="delivery_failed_reply",
                    default=DEFAULT_DELIVERY_FAILED_REPLY,
                    help="平台发送失败时回复给用户的文本。",
                    type=str,
                    label="发送失败提示",
                    order=100,
                ),
            ]
        ),
    ).to_dict(),
)


async def _is_contact_owner_message(event: Event) -> bool:
    try:
        text = event.get_plaintext()
    except Exception:  # noqa: BLE001
        return False
    config = get_contact_owner_config()
    return text.lstrip().startswith(config.contact_prefix)


_contact_owner = on_message(
    Rule(_is_contact_owner_message),
    priority=8,
    block=False,
)


@_contact_owner.handle()
async def handle_contact_owner(bot: Bot, event: Event, matcher: Matcher) -> None:
    result = await handle_contact_owner_event(
        bot,
        event,
        message_text=_event_plaintext(event),
        config=get_contact_owner_config(),
    )
    if result.reply:
        await matcher.send(result.reply)
    if result.should_stop_propagation:
        matcher.stop_propagation()


def _event_plaintext(event: Event) -> str:
    try:
        return event.get_plaintext()
    except Exception:  # noqa: BLE001
        return ""


__all__ = ["_contact_owner", "handle_contact_owner"]
