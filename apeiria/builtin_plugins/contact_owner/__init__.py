from __future__ import annotations

from contextlib import suppress

from nonebot import get_plugin_config
from nonebot.adapters import Bot, Event  # noqa: TC002
from nonebot.log import logger
from nonebot.matcher import Matcher  # noqa: TC002
from nonebot.plugin import PluginMetadata
from nonebot.plugin.on import on_message
from nonebot.rule import Rule
from pydantic import BaseModel, ConfigDict

from apeiria.plugin.metadata.api import (
    ConfigExtra,
    HelpExtra,
    PluginExtraData,
    PluginType,
    RegisterConfig,
    UiExtra,
)


class ContactOwnerConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")
    contact_prefix: str = "联系主人"
    owner_target: str = ""
    message_prefix: str = ""


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
                    default="联系主人",
                    help="触发联系主人的文本前缀。",
                    type=str,
                    label="联系前缀",
                    order=10,
                ),
                RegisterConfig(
                    key="owner_target",
                    default="",
                    help="主人目标，格式为 qq:QQ号。",
                    type=str,
                    label="主人目标",
                    order=20,
                ),
                RegisterConfig(
                    key="message_prefix",
                    default="",
                    help="转发消息前添加的前缀文本。",
                    type=str,
                    label="消息前缀",
                    order=30,
                ),
            ]
        ),
    ).to_dict(),
)


def _get_config() -> ContactOwnerConfig:
    return get_plugin_config(ContactOwnerConfig)


def _parse_owner_target(value: str) -> tuple[str, str] | None:
    text = value.strip()
    if ":" not in text:
        return None
    scope, target_id = text.split(":", maxsplit=1)
    scope = scope.strip().lower()
    target_id = target_id.strip()
    if not scope or not target_id:
        return None
    return scope, target_id


def _format_owner_message(body: str, event: Event, prefix: str) -> str:
    lines = ["收到一条联系主人留言：", ""]
    if prefix:
        lines.append(prefix)
    lines.append(body)
    lines.append("")
    lines.append("来源：")
    with suppress(Exception):
        lines.append(f"- 用户 ID：{event.get_user_id()}")
    with suppress(Exception):
        sid = str(event.get_session_id())
        if sid and lines:
            last = lines[-1]
            user_part = last.removeprefix("- 用户 ID：")
            if sid != user_part:
                lines.append(f"- 会话 ID：{sid}")
    return "\n".join(lines)


async def _deliver_to_qq(
    bot: Bot,
    event: Event,
    body: str,
    target_id: str,
    prefix: str,
) -> bool:
    message = _format_owner_message(body, event, prefix)
    try:
        qq_id = int(target_id)
    except (TypeError, ValueError):
        return False
    with suppress(Exception):
        await bot.send_private_msg(user_id=qq_id, message=message)
        return True
    logger.debug("联系主人发送失败")
    return False


async def _is_contact_owner_message(event: Event) -> bool:
    config = _get_config()
    with suppress(Exception):
        text = event.get_plaintext()
        return text.lstrip().startswith(config.contact_prefix)
    return False


_contact_owner = on_message(
    Rule(_is_contact_owner_message),
    priority=8,
    block=False,
)


@_contact_owner.handle()
async def handle_contact_owner(bot: Bot, event: Event, matcher: Matcher) -> None:
    config = _get_config()

    try:
        text = event.get_plaintext()
    except Exception:  # noqa: BLE001
        return
    body = text.lstrip()[len(config.contact_prefix) :].strip()

    if not body:
        await matcher.send("请在前缀后写下要留言的内容。")
        return

    if not config.owner_target:
        await matcher.send("主人联系方式未配置，暂时无法留言。")
        return

    target = _parse_owner_target(config.owner_target)
    if target is None:
        await matcher.send("主人联系方式配置有误，暂时无法留言。")
        return

    scope, target_id = target

    if scope == "qq":
        ok = await _deliver_to_qq(bot, event, body, target_id, config.message_prefix)
    else:
        await matcher.send("当前平台暂不支持联系主人。")
        return

    if ok:
        await matcher.send("已给主人留言。")
    else:
        await matcher.send("留言发送失败，请稍后再试。")


__all__ = ["_contact_owner", "handle_contact_owner"]
