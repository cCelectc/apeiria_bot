from __future__ import annotations

from contextlib import suppress

import nonebot
from arclet.alconna import Args, CommandMeta, Subcommand
from nonebot import on_request, require
from nonebot.adapters import Bot, Event  # noqa: TC002
from nonebot.log import logger
from nonebot.permission import SUPERUSER
from nonebot.plugin import PluginMetadata, on_message
from nonebot.rule import Rule
from nonebot_plugin_alconna import Alconna, MultiVar, on_alconna

require("nonebot_plugin_uninfo")
from nonebot_plugin_uninfo import Uninfo  # noqa: TC002

from apeiria.utils.session import resolve_superuser_targets

from .config import FriendshipConfig, get_friendship_config
from .models import PendingRequest
from .pending import (
    add_pending,
    find_by_notified_msg,
    get_pending,
    load_all,
    remove_pending,
    update_notified,
)
from .providers import get_provider_by_key, resolve_provider

TITLE_MAP = {"friend": "好友申请", "group_add": "加群申请", "group_invite": "入群邀请"}
KIND_LABEL_MAP = {"friend": "好友", "group_add": "加群", "group_invite": "邀请"}

__plugin_meta__ = PluginMetadata(
    name="好友请求管理",
    description="监听好友申请/入群申请/群邀请并通知超管，支持同意/拒绝操作。",
    homepage="https://github.com/Cccc-owo/apeiria_bot",
    usage=(
        "自动转发请求通知给超级用户。\n"
        "使用 /申请 查看待处理请求列表。\n"
        "使用 /申请 同意 <id> [备注] 或 /申请 拒绝 <id> [理由] 处理请求。\n"
        "也可直接回复通知消息发送「同意」或「拒绝」。"
    ),
    type="application",
    config=FriendshipConfig,
    supported_adapters={"~onebot.v11", "~satori", "~milky"},
)

_request = on_request(priority=2, block=False)

_apply = on_alconna(
    Alconna(
        "申请",
        Subcommand(
            "同意",
            Args["id", str],
            Args["remark?", MultiVar(str, "*")],
            alias=["approve"],
        ),
        Subcommand(
            "拒绝",
            Args["id", str],
            Args["reason?", MultiVar(str, "*")],
            alias=["reject"],
        ),
        meta=CommandMeta(description="管理好友/群请求"),
    ),
    aliases={"requests"},
    use_cmd_start=True,
    priority=2,
    block=True,
)


async def _reply_rule(bot: Bot, event: Event) -> bool:
    if not await SUPERUSER(bot, event):
        return False
    reply = getattr(event, "reply", None)
    if reply is None:
        return False
    replied_id = str(getattr(reply, "message_id", ""))
    if not replied_id:
        return False
    return await find_by_notified_msg(replied_id) is not None


_reply_handler = on_message(
    Rule(_reply_rule),
    priority=2,
    block=True,
)


@_request.handle()
async def handle_request(
    bot: Bot,
    event: Event,
    session: Uninfo,
) -> None:
    config = get_friendship_config()
    if not config.enabled:
        return

    provider = resolve_provider(bot, event)
    if provider is None:
        return

    info = provider.extract(bot, event)
    if info is None:
        return

    try:
        nick = session.user.nick or session.user.name or info.requester_id
    except Exception:  # noqa: BLE001
        nick = info.requester_id

    pending = PendingRequest(
        id="",
        provider_key=provider.key,
        bot_self_id=bot.self_id,
        scope=str(session.scope),
        raw_flag=info.raw_flag,
        kind=info.kind,
        requester_id=info.requester_id,
        requester_name=nick,
        comment=info.comment,
        sub_type=info.sub_type,
        group_id=info.group_id,
        group_name=info.group_name,
    )

    await add_pending(pending)
    logger.info(
        "saved pending request {} ({}/{})",
        pending.id,
        pending.kind,
        pending.requester_id,
    )

    if config.notify_superusers:
        targets = resolve_superuser_targets(bot)
        if not targets:
            logger.warning("no same-platform superusers to notify for {}", info.kind)
            return

        title = TITLE_MAP[info.kind]
        msg = format_notification(pending, title)

        for target_id in targets:
            try:
                result = await bot.send_private_msg(user_id=int(target_id), message=msg)
                if isinstance(result, dict):
                    msg_id = str(result.get("message_id", ""))
                else:
                    msg_id = ""
                await update_notified(pending.id, target_id, msg_id)
            except Exception:  # noqa: BLE001
                pass


@_apply.handle()
async def handle_apply(  # noqa: C901, PLR0912
    bot: Bot,
    event: Event,
) -> None:
    config = get_friendship_config()
    if not config.enabled:
        await _apply.finish("好友请求管理已禁用")

    if not await SUPERUSER(bot, event):
        await _apply.finish("仅限超级用户使用")

    sub_result = _apply.get_subcommand(event)
    if sub_result is None:
        pending_list = await load_all()
        pending_list = [r for r in pending_list if r.status == "pending"]
        if not pending_list:
            await _apply.finish("暂无待处理请求")
        lines = []
        for r in pending_list:
            kind_label = KIND_LABEL_MAP[r.kind]
            scope_str = r.scope.replace("QQClient", "QQ")
            lines.append(
                f"[{r.id}] {kind_label}"
                f" — {r.requester_name}({r.requester_id})"
                f" | {scope_str}"
                + (f" | 群:{r.group_id}" if r.group_id else "")
                + (f" | {r.comment}" if r.comment else "")
            )
        suffix = "\n回复「同意/拒绝」<id> 或使用 /申请 同意/拒绝 <id>"
        await _apply.finish("待处理请求:\n" + "\n".join(lines) + suffix)

    sub_name = sub_result.name
    args = sub_result.args

    request_id = args.get("id", "").strip() if isinstance(args, dict) else ""
    if not request_id:
        await _apply.finish("请指定请求 ID，如 /申请 同意 f1")

    pending = await get_pending(request_id)
    if pending is None:
        await _apply.finish(f"未找到请求: {request_id}")
    if pending.status != "pending":
        await _apply.finish(f"请求 {request_id} 已处理（{pending.status}）")

    provider = get_provider_by_key(pending.provider_key)
    if provider is None:
        await _apply.finish(f"不支持的请求来源: {pending.provider_key}")

    target_bot = nonebot.get_bot(pending.bot_self_id)
    if target_bot is None:
        await _apply.finish(f"目标 bot {pending.bot_self_id} 不在线")

    if sub_name in ("同意", "approve"):
        remark = " ".join(args.get("remark", [])) if "remark" in (args or {}) else ""
        result = await provider.approve(target_bot, pending, remark=remark)
    elif sub_name in ("拒绝", "reject"):
        reason = " ".join(args.get("reason", [])) if "reason" in (args or {}) else ""
        result = await provider.reject(target_bot, pending, reason=reason)
    else:
        await _apply.finish("未知操作")

    if result.success:
        with suppress(Exception):
            await remove_pending(request_id)
        await _apply.finish(f"已完成: {sub_name} {request_id}")
    else:
        await _apply.finish(f"操作失败: {result.message}")


@_reply_handler.handle()
async def handle_reply_action(
    bot: Bot,
    event: Event,
) -> None:
    if not await SUPERUSER(bot, event):
        return

    reply = getattr(event, "reply", None)
    if reply is None:
        return
    replied_msg_id = str(getattr(reply, "message_id", ""))
    pending = await find_by_notified_msg(replied_msg_id)
    if pending is None:
        return

    text = ""
    with suppress(Exception):
        text = event.get_plaintext().strip().lower()

    keywords_agree = {"同意", "approve", "yes", "通过", "ok"}
    keywords_reject = {"拒绝", "reject", "no", "驳回"}

    target_bot = nonebot.get_bot(pending.bot_self_id)
    if target_bot is None:
        await _reply_handler.finish("目标 bot 不在线")

    provider = get_provider_by_key(pending.provider_key)
    if provider is None:
        await _reply_handler.finish("不支持的请求来源")

    if text in keywords_agree:
        result = await provider.approve(target_bot, pending)
    elif text in keywords_reject:
        result = await provider.reject(target_bot, pending)
    else:
        await _reply_handler.finish("回复通知消息「同意」或「拒绝」来处理请求")
        return

    if result.success:
        with suppress(Exception):
            await remove_pending(pending.id)
        await _reply_handler.finish(
            f"已{'同意' if text in keywords_agree else '拒绝'} {pending.id}"
        )
    else:
        await _reply_handler.finish(f"操作失败: {result.message}")


def format_notification(
    pending: PendingRequest,
    title: str,
) -> str:
    msg = f"【{title}】\n"
    msg += f"ID: {pending.id}\n"
    msg += f"用户: {pending.requester_name}({pending.requester_id})\n"
    if pending.group_id:
        group_label = pending.group_name or pending.group_id
        msg += f"群: {group_label}\n"
    if pending.comment:
        msg += f"留言: {pending.comment}\n"
    msg += f"平台: {pending.scope}\n"
    msg += "\n回复本消息「同意」或「拒绝」来处理此请求"
    return msg


__all__ = ["_apply", "_reply_handler", "_request"]
