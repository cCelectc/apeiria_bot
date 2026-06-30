from __future__ import annotations

from contextlib import suppress

from nonebot import require
from nonebot.adapters import Bot, Event  # noqa: TC002
from nonebot.log import logger
from nonebot.matcher import Matcher  # noqa: TC002
from nonebot.permission import SUPERUSER
from nonebot.plugin import PluginMetadata
from nonebot.plugin.on import on_message
from nonebot.rule import Rule
from nonebot.typing import T_State  # noqa: TC002
from nonebot_plugin_alconna import Alconna, CommandMeta, on_alconna

from apeiria.plugin.metadata.api import (
    CommandDeclaration,
    ConfigExtra,
    HelpExtra,
    PluginExtraData,
    PluginType,
    RegisterConfig,
    UiExtra,
)

from .config import TriggerReplyConfig, get_trigger_reply_config
from .loader import _ensure_loaded, _refresh_rules
from .models import TriggerEntry, TriggerInput
from .service import _evaluate, _platform_alias

require("nonebot_plugin_localstore")

__plugin_meta__ = PluginMetadata(
    name="触发回复",
    description="按独立规则文件响应特定消息。",
    homepage="https://github.com/Cccc-owo/apeiria_bot",
    usage="在本插件规则文件中配置 entry、match 与 reply 后自动回复。",
    type="application",
    config=TriggerReplyConfig,
    supported_adapters=None,
    extra=PluginExtraData(
        author="apeiria",
        version="0.1.0",
        plugin_type=PluginType.NORMAL,
        help=HelpExtra(
            category="基础功能",
            introduction="按配置规则响应消息文本。",
        ),
        ui=UiExtra(label="触发回复", order=19),
        commands=[
            CommandDeclaration(
                name="重载回复",
                description="重新加载触发回复规则文件。",
                aliases=["tr"],
            )
        ],
        config=ConfigExtra(
            fields=[
                RegisterConfig(
                    key="enabled",
                    default=True,
                    help="是否启用触发回复。",
                    type=bool,
                    label="启用",
                    order=10,
                ),
                RegisterConfig(
                    key="priority",
                    default=12,
                    help="NoneBot matcher 优先级。",
                    type=int,
                    label="优先级",
                    order=20,
                ),
                RegisterConfig(
                    key="rules_file",
                    default="rules.toml",
                    help="规则文件路径。",
                    type=str,
                    label="规则文件",
                    order=40,
                ),
                RegisterConfig(
                    key="debug",
                    default=False,
                    help="启用后记录调试日志。",
                    type=bool,
                    label="调试日志",
                    order=50,
                ),
            ]
        ),
        required_plugins=["nonebot_plugin_localstore"],
    ).to_dict(),
)


def _extract_input(bot: Bot, event: Event) -> TriggerInput | None:
    with suppress(Exception):
        if event.get_type() != "message":
            return None
    user_id = None
    group_id = None
    bot_id = None
    with suppress(Exception):
        user_id = str(event.get_user_id())
    with suppress(Exception):
        gid = str(event.get_session_id())
        if gid != user_id:
            group_id = gid
    with suppress(Exception):
        bot_id = bot.self_id
    message_text = ""
    with suppress(Exception):
        message_text = str(event.get_message())
    plaintext = ""
    with suppress(Exception):
        plaintext = str(event.get_plaintext())
    is_to_me = False
    with suppress(Exception):
        is_to_me = event.is_tome()
    adapter_name = ""
    with suppress(Exception):
        adapter_name = bot.adapter.get_name().split(maxsplit=1)[0].lower()
    platform = _platform_alias(adapter_name)
    return TriggerInput(
        platform=platform,
        bot_id=str(bot_id) if bot_id else None,
        user_id=user_id,
        group_id=group_id,
        message_text=message_text,
        plaintext=plaintext,
        is_to_me=is_to_me,
    )


async def _rule_checker(bot: Bot, event: Event, state: T_State) -> bool:
    config = get_trigger_reply_config()
    if not config.enabled:
        return False
    trigger = _extract_input(bot, event)
    if trigger is None:
        if config.debug:
            logger.debug("触发回复跳过: 不支持的消息输入")
        return False
    entries = _ensure_loaded(config)
    if not entries:
        return False
    if not _fast_check(trigger, entries):
        return False
    result = _evaluate(trigger, entries)
    if result is None:
        if config.debug:
            logger.debug("触发回复跳过: 无匹配规则")
        return False
    reply, matched_entry = result
    state["_trigger_reply_text"] = reply
    state["_trigger_reply_entry"] = matched_entry
    return True


def _fast_check(  # noqa: C901
    trigger: TriggerInput, entries: tuple[TriggerEntry, ...]
) -> bool:
    has_regex = False
    candidates = {trigger.plaintext.lower(), trigger.message_text.lower()}
    for entry in entries:
        if not entry.enabled:
            continue
        for match in entry.matches:
            if match.type == "regex":
                has_regex = True
                continue
            pattern = match.pattern or ""
            if not pattern:
                continue
            kw = pattern.lower() if match.ignore_case else pattern
            for text in candidates:
                if match.type == "full" and text == kw:
                    return True
                if match.type == "start" and text.startswith(kw):
                    return True
                if match.type == "end" and text.endswith(kw):
                    return True
                if match.type == "fuzzy" and kw in text:
                    return True
    return bool(has_regex)


_message = on_message(
    Rule(_rule_checker),
    priority=12,
    block=False,
)
_reload = on_alconna(
    Alconna(
        "重载回复",
        meta=CommandMeta(description="重新加载触发回复规则文件"),
    ),
    aliases={"tr"},
    permission=SUPERUSER,
    use_cmd_start=True,
    priority=5,
    block=True,
)


@_message.handle()
async def handle_trigger_message(matcher: Matcher, state: T_State) -> None:
    reply_text: str = state.get("_trigger_reply_text", "")
    if not reply_text:
        return
    entry = state.get("_trigger_reply_entry")
    if entry is not None and getattr(entry, "block", False):
        matcher.stop_propagation()
    await matcher.send(reply_text)


@_reload.handle()
async def handle_trigger_reply_reload() -> None:
    config = get_trigger_reply_config()
    count, errors = _refresh_rules(config)
    if errors:
        await _reload.finish(
            f"触发回复规则已重载：{count} 条可用，{len(errors)} 个错误。"
        )
    await _reload.finish(f"触发回复规则已重载：{count} 条可用。")


__all__ = [
    "_message",
    "_reload",
    "handle_trigger_message",
    "handle_trigger_reply_reload",
]
