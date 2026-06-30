from __future__ import annotations

from contextlib import suppress

from nonebot import get_driver
from nonebot.adapters import Bot, Event  # noqa: TC002
from nonebot.log import logger
from nonebot.matcher import Matcher  # noqa: TC002
from nonebot.permission import SUPERUSER
from nonebot.plugin import PluginMetadata
from nonebot.plugin.on import on_fullmatch, on_message
from nonebot.rule import Rule

from apeiria.plugin.metadata.api import (
    CommandDeclaration,
    ConfigExtra,
    HelpExtra,
    PluginExtraData,
    PluginType,
    RegisterConfig,
    UiExtra,
)

from .config import SelfRevokeConfig, get_self_revoke_config
from .providers import _resolve_provider

__plugin_meta__ = PluginMetadata(
    name="撤回消息",
    description="用户引用回复机器人消息来触发撤回。",
    homepage="https://github.com/Cccc-owo/apeiria_bot",
    usage="回复机器人的消息并发送「撤回」或「revoke」。",
    type="application",
    config=SelfRevokeConfig,
    supported_adapters=None,
    extra=PluginExtraData(
        author="apeiria",
        version="0.1.0",
        plugin_type=PluginType.NORMAL,
        help=HelpExtra(
            category="基础功能",
            introduction="用户引用回复机器人消息触发撤回。",
        ),
        ui=UiExtra(label="撤回消息", order=15),
        commands=[
            CommandDeclaration(
                name="撤回",
                description="撤回引用回复的机器人消息。",
                aliases=["revoke"],
                custom_prefix="",
            ),
            CommandDeclaration(
                name="revoke",
                description="撤回引用回复的机器人消息。",
                aliases=["撤回"],
            ),
        ],
        config=ConfigExtra(
            fields=[
                RegisterConfig(
                    key="permission",
                    default="public",
                    help="撤回权限。",
                    type=str,
                    choices=["public", "superuser"],
                    choice_labels={
                        "public": "所有人",
                        "superuser": "仅超级用户",
                    },
                    label="权限",
                    order=10,
                ),
                RegisterConfig(
                    key="revoke_trigger_message",
                    default=False,
                    help="撤回目标消息后是否同时撤回触发消息本身。",
                    type=bool,
                    label="撤回触发消息",
                    order=20,
                ),
                RegisterConfig(
                    key="feedback",
                    default="silent",
                    help="操作反馈方式。",
                    type=str,
                    choices=["silent", "reaction"],
                    choice_labels={
                        "silent": "静默",
                        "reaction": "表情反应",
                    },
                    label="反馈方式",
                    order=30,
                ),
            ]
        ),
    ).to_dict(),
)


async def _is_superuser_event(bot: Bot, event: Event) -> bool:
    with suppress(Exception):
        return await SUPERUSER(bot, event)
    return False


def _strip_command_prefix(text: str) -> str | None:
    try:
        command_start = getattr(get_driver().config, "command_start", {"/"})
    except Exception:  # noqa: BLE001
        command_start = {"/"}
    if isinstance(command_start, str):
        command_start = {command_start}
    if not isinstance(command_start, (set, list, tuple)):
        command_start = {"/"}
    prefixes = sorted(
        (str(item) for item in command_start if str(item)),
        key=len,
        reverse=True,
    )
    for prefix in prefixes:
        if text.startswith(prefix):
            return text[len(prefix) :].strip()
    return None


async def _is_prefixed_revoke(event: Event) -> bool:
    with suppress(Exception):
        text = event.get_plaintext().strip()
        prefix = _strip_command_prefix(text)
        return prefix.lower() in {"撤回", "revoke"} if prefix is not None else False
    return False


_prefixless_revoke = on_fullmatch(
    ("撤回", "revoke"),
    ignorecase=True,
    priority=8,
    block=False,
)
_prefixed_revoke = on_message(
    Rule(_is_prefixed_revoke),
    priority=8,
    block=False,
)


@_prefixless_revoke.handle()
@_prefixed_revoke.handle()
async def handle_revoke(  # noqa: C901
    bot: Bot,
    event: Event,
    matcher: Matcher,  # noqa: ARG001
) -> None:
    config = get_self_revoke_config()
    provider = _resolve_provider(bot, event)
    if provider is None:
        return

    target = await provider.get_reply_target(bot, event)
    if target is None:
        return

    if config.permission == "superuser" and not await _is_superuser_event(bot, event):
        if config.feedback == "reaction":
            with suppress(Exception):
                await provider.apply_feedback(bot, event, kind="failure")
        return

    if not await provider.is_bot_authored(bot, event, target):
        if config.feedback == "reaction":
            with suppress(Exception):
                await provider.apply_feedback(bot, event, kind="failure")
        return

    revoke_result = await provider.revoke_message(bot, event, target)
    if not revoke_result.success:
        logger.debug("撤回目标消息失败: {}", revoke_result.reason)
        if config.feedback == "reaction":
            with suppress(Exception):
                await provider.apply_feedback(bot, event, kind="failure")
        return

    if config.revoke_trigger_message:
        with suppress(Exception):
            await provider.revoke_trigger_message(bot, event)

    if not config.revoke_trigger_message and config.feedback == "reaction":
        with suppress(Exception):
            await provider.apply_feedback(bot, event, kind="success")


__all__ = ["_prefixed_revoke", "_prefixless_revoke", "handle_revoke"]
