from __future__ import annotations

from contextlib import suppress

from nonebot import get_plugin_config
from nonebot.adapters import Bot, Event  # noqa: TC002
from nonebot.log import logger
from nonebot.matcher import Matcher  # noqa: TC002
from nonebot.plugin import PluginMetadata
from nonebot.plugin.on import on_request
from pydantic import BaseModel, ConfigDict

from apeiria.plugin.metadata.api import (
    ConfigExtra,
    HelpExtra,
    PluginExtraData,
    PluginType,
    RegisterConfig,
    UiExtra,
)
from apeiria.utils.superuser import get_superuser_set


class FriendshipConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")
    enabled: bool = True


__plugin_meta__ = PluginMetadata(
    name="好友请求通知",
    description="将好友请求和群邀请通知转发给超级用户。",
    homepage="https://github.com/Cccc-owo/apeiria_bot",
    usage="收到好友申请或群邀请时自动转发给超级用户。",
    type="application",
    config=FriendshipConfig,
    supported_adapters=None,
    extra=PluginExtraData(
        author="apeiria",
        version="0.1.0",
        plugin_type=PluginType.NORMAL,
        help=HelpExtra(
            category="基础功能",
            introduction="把好友申请和群邀请通知转发给超级用户。",
        ),
        ui=UiExtra(label="好友请求通知", order=18),
        config=ConfigExtra(
            fields=[
                RegisterConfig(
                    key="enabled",
                    default=True,
                    help="是否启用好友请求通知。",
                    type=bool,
                    label="启用",
                    order=10,
                ),
            ]
        ),
    ).to_dict(),
)


def _get_config() -> FriendshipConfig:
    return get_plugin_config(FriendshipConfig)


def _is_onebot_v11_request(bot: Bot, event: Event) -> bool:
    with suppress(Exception):
        adapter_name = bot.adapter.get_name().split(maxsplit=1)[0].lower()
        if adapter_name != "onebotv11":
            return False
    with suppress(Exception):
        return event.get_type() == "request"
    return False


_request = on_request(priority=2, block=False)


@_request.handle()
async def handle_request(bot: Bot, event: Event, matcher: Matcher) -> None:  # noqa: ARG001
    config = _get_config()
    if not config.enabled:
        return

    if not _is_onebot_v11_request(bot, event):
        return

    request_type = getattr(event, "request_type", None)
    user_id = getattr(event, "user_id", None)
    comment = getattr(event, "comment", "") or ""
    group_id = getattr(event, "group_id", None)
    flag = getattr(event, "flag", None)
    sub_type = getattr(event, "sub_type", None)

    if request_type == "friend":
        title = "好友申请"
        detail = f"用户 {user_id} 申请添加好友"
        if comment:
            detail += f"\n留言: {comment}"
        detail += f"\nflag: {flag}"
    elif request_type == "group" and sub_type == "invite":
        title = "入群邀请"
        detail = f"用户 {user_id} 邀请机器人加入群 {group_id}"
        detail += f"\nflag: {flag}"
    elif request_type == "group" and sub_type == "add":
        title = "加群申请"
        detail = f"用户 {user_id} 申请加入群 {group_id}"
        if comment:
            detail += f"\n留言: {comment}"
        detail += f"\nflag: {flag}"
    else:
        return

    message = f"【{title}通知】\n{detail}"
    logger.info("收到{}: {}", title, detail)

    superusers = get_superuser_set()
    if not superusers:
        logger.warning("无超级用户配置，无法转发请求通知")
        return

    for superuser_id in superusers:
        with suppress(Exception):
            await bot.send_private_msg(user_id=int(superuser_id), message=message)


__all__ = ["_request", "handle_request"]
