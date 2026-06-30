from __future__ import annotations

from collections import deque
from contextlib import suppress
from time import monotonic

from arclet.alconna import Args, CommandMeta
from nonebot import require
from nonebot.adapters import Bot  # noqa: TC002
from nonebot.log import logger
from nonebot.plugin import PluginMetadata, inherit_supported_adapters
from nonebot_plugin_alconna import (
    Alconna,
    Match,
    MultiVar,
    Target,
    UniMessage,
    on_alconna,
)

require("nonebot_plugin_uninfo")
from nonebot_plugin_uninfo import Uninfo  # noqa: TC002

from apeiria.utils.session import resolve_superuser_targets

from .config import RelayConfig, get_relay_config

__plugin_meta__ = PluginMetadata(
    name="传话",
    description="允许用户通过命令向指定目标（默认=超管）发送单向消息。",
    homepage="https://github.com/Cccc-owo/apeiria_bot",
    usage="发送 /传话 <内容> 向主人留言。",
    type="application",
    config=RelayConfig,
    supported_adapters=inherit_supported_adapters(
        "nonebot_plugin_alconna", "nonebot_plugin_uninfo"
    ),
)

_rates: dict[str, deque[float]] = {}

_relay = on_alconna(
    Alconna(
        "传话",
        Args["message", MultiVar(str, "*")],
        meta=CommandMeta(description="向指定目标发送单向消息"),
    ),
    use_cmd_start=True,
    priority=5,
    block=True,
)


def _rate_check(user_id: str, count: int, window: float) -> bool:
    if count <= 0:
        return True
    now = monotonic()
    history = _rates.get(user_id)
    if history is None:
        history = deque[float]()
        _rates[user_id] = history
    while history and now - history[0] > window:
        history.popleft()
    return len(history) < count


def _rate_push(user_id: str) -> None:
    _rates.setdefault(user_id, deque[float]()).append(monotonic())


def _parse_target(value: str) -> tuple[str, str] | None:
    text = value.strip()
    if ":" not in text:
        return None
    scope, tid = text.split(":", maxsplit=1)
    scope = scope.strip()
    tid = tid.strip()
    if not scope or not tid:
        return None
    return scope, tid


def _build_source_line(session: Uninfo) -> str:
    nick = ""
    with suppress(Exception):
        nick = session.user.nick or session.user.name or ""
    user_display = f"{nick}({session.user.id})" if nick else session.user.id

    if session.scene.is_group:
        sname = ""
        with suppress(Exception):
            sname = session.scene.name or ""
        gd = f"{sname}({session.scene.id})" if sname else session.scene.id
        return f"来自群 {gd} 用户 {user_display}"
    return f"来自用户 {user_display}"


@_relay.handle()
async def handle_relay(
    bot: Bot,
    session: Uninfo,
    message: Match[tuple[str, ...]],
) -> None:
    config = get_relay_config()

    if not message.available:
        await _relay.finish("请在 /传话 后写上要留言的内容。")
        return
    body = " ".join(message.result).strip()
    if not body:
        await _relay.finish("请在 /传话 后写上要留言的内容。")
        return

    user_id = session.user.id
    count = config.rate_limit_count
    window = float(config.rate_limit_window)
    if not _rate_check(user_id, count, window):
        await _relay.finish("传话太快了，请稍后再试。")
        return

    target_scope: str | None = None
    target_id: str | None = None

    if config.target:
        parsed = _parse_target(config.target)
        if parsed is None:
            await _relay.finish("目标配置格式有误，格式应为 scope:id。")
            return
        target_scope, target_id = parsed
    else:
        targets = resolve_superuser_targets(bot)
        if not targets:
            await _relay.finish("无可用目标，请检查超管配置。")
            return
        target_id = targets[0]
        target_scope = str(session.scope)

    source_line = _build_source_line(session)
    prefix = config.message_prefix
    full_msg = f"{source_line} 留言:\n{body}"
    if prefix:
        full_msg = f"{prefix}\n\n{full_msg}"

    _rate_push(user_id)

    try:
        await UniMessage.text(full_msg).send(
            target=Target(id=target_id, private=True, scope=target_scope)
        )
        await _relay.finish("已发送留言。")
    except Exception as exc:  # noqa: BLE001
        logger.warning("relay delivery failed: {}", exc)
        await _relay.finish("留言发送失败，请稍后再试。")


__all__ = ["_relay", "handle_relay"]
