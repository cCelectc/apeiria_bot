"""Contact approval built-in plugin."""

from __future__ import annotations

from nonebot.adapters import Bot, Event  # noqa: TC002
from nonebot.matcher import Matcher  # noqa: TC002
from nonebot.plugin import PluginMetadata
from nonebot.plugin.on import on_message, on_request
from nonebot.rule import Rule

from apeiria.plugins.metadata.api import (
    CommandDeclaration,
    ConfigExtra,
    HelpExtra,
    PluginExtraData,
    PluginType,
    RegisterConfig,
    UiExtra,
)

from .commands import parse_approval_command
from .config import (
    DEFAULT_APPROVAL_PREFIX,
    DEFAULT_MISSING_TARGET_REPLY,
    DEFAULT_PLATFORM_FAILED_REPLY,
    DEFAULT_TICKET_EXPIRATION_MINUTES,
    DEFAULT_TICKET_NOT_FOUND_REPLY,
    DEFAULT_UNAUTHORIZED_REPLY,
    ContactApprovalConfig,
    get_contact_approval_config,
)
from .service import handle_approval_message, handle_request_event

__plugin_meta__ = PluginMetadata(
    name="关系审批",
    description="通过主人私聊和群内审批卡片处理好友申请与加群请求。",
    homepage="https://github.com/Cccc-owo/apeiria_bot",
    usage=(
        "引用审批卡片回复「同意」「拒绝 原因」「忽略」「详情」，"
        "或发送「审批」查看待办。"
    ),
    type="application",
    config=ContactApprovalConfig,
    supported_adapters=None,
    extra=PluginExtraData(
        author="apeiria",
        version="0.1.0",
        plugin_type=PluginType.NORMAL,
        help=HelpExtra(
            category="基础功能",
            introduction="把好友申请、机器人入群邀请和群成员加群申请整理成可追踪审批。",
        ),
        ui=UiExtra(label="关系审批", order=18),
        commands=[
            CommandDeclaration(
                name="审批",
                description="查看待处理关系审批。",
                aliases=["list"],
                custom_prefix="",
            ),
            CommandDeclaration(
                name="同意",
                description="同意引用或指定编号的审批。",
                aliases=["允许", "通过", "approve", "pass"],
                custom_prefix="",
            ),
            CommandDeclaration(
                name="拒绝",
                description="拒绝引用或指定编号的审批。",
                aliases=["reject"],
                custom_prefix="",
            ),
            CommandDeclaration(
                name="忽略",
                description="本地关闭引用或指定编号的审批。",
                aliases=["ignore"],
                custom_prefix="",
            ),
            CommandDeclaration(
                name="详情",
                description="查看引用或指定编号的审批详情。",
                aliases=["detail"],
                custom_prefix="",
            ),
        ],
        config=ConfigExtra(
            fields=[
                RegisterConfig(
                    key="owner_targets",
                    default=[],
                    help=(
                        "主人私聊目标列表，格式为 qq:QQ号；"
                        "留空时尝试从 superusers 推导 QQ 号。"
                    ),
                    type=list,
                    item_type=str,
                    label="主人目标",
                    order=10,
                ),
                RegisterConfig(
                    key="friend_requests_enabled",
                    default=True,
                    help="是否处理好友申请。",
                    type=bool,
                    label="好友申请",
                    order=20,
                ),
                RegisterConfig(
                    key="bot_group_invites_enabled",
                    default=True,
                    help="是否处理机器人入群邀请。",
                    type=bool,
                    label="入群邀请",
                    order=30,
                ),
                RegisterConfig(
                    key="group_join_requests_enabled",
                    default=True,
                    help="是否处理群成员加群申请。",
                    type=bool,
                    label="加群申请",
                    order=40,
                ),
                RegisterConfig(
                    key="group_join_gate_mode",
                    default="whitelist",
                    help="群成员加群申请通知门禁模式。",
                    type=str,
                    choices=["whitelist", "blacklist"],
                    choice_labels={
                        "whitelist": "白名单",
                        "blacklist": "黑名单",
                    },
                    label="群门禁模式",
                    order=50,
                ),
                RegisterConfig(
                    key="group_join_gate_ids",
                    default=[],
                    help="群成员加群申请通知门禁群号列表。",
                    type=list,
                    item_type=str,
                    label="门禁群号",
                    order=60,
                ),
                RegisterConfig(
                    key="suppressed_group_join_action",
                    default="ignore",
                    help="群成员申请被门禁静默时的处理方式。",
                    type=str,
                    choices=["ignore", "reject"],
                    choice_labels={"ignore": "忽略", "reject": "拒绝"},
                    label="静默动作",
                    order=70,
                ),
                RegisterConfig(
                    key="suppressed_group_join_reject_reason",
                    default="",
                    help="静默动作设为拒绝时传给平台的拒绝理由。",
                    type=str,
                    label="静默拒绝理由",
                    order=80,
                ),
                RegisterConfig(
                    key="ticket_expiration_minutes",
                    default=DEFAULT_TICKET_EXPIRATION_MINUTES,
                    help="审批票据过期分钟数。",
                    type=int,
                    label="过期时间",
                    order=90,
                ),
                RegisterConfig(
                    key="approval_prefix",
                    default=DEFAULT_APPROVAL_PREFIX,
                    help="列表命令触发词。",
                    type=str,
                    label="审批命令",
                    order=100,
                ),
                RegisterConfig(
                    key="missing_target_reply",
                    default=DEFAULT_MISSING_TARGET_REPLY,
                    help="未引用审批卡片且未带编号时的提示。",
                    type=str,
                    label="缺少目标提示",
                    order=110,
                ),
                RegisterConfig(
                    key="ticket_not_found_reply",
                    default=DEFAULT_TICKET_NOT_FOUND_REPLY,
                    help="审批编号不存在时的提示。",
                    type=str,
                    label="未找到提示",
                    order=120,
                ),
                RegisterConfig(
                    key="unauthorized_reply",
                    default=DEFAULT_UNAUTHORIZED_REPLY,
                    help="无权限处理审批时的提示。",
                    type=str,
                    label="无权限提示",
                    order=130,
                ),
                RegisterConfig(
                    key="platform_failed_reply",
                    default=DEFAULT_PLATFORM_FAILED_REPLY,
                    help="平台审批 API 调用失败时的提示。",
                    type=str,
                    label="平台失败提示",
                    order=140,
                ),
            ]
        ),
    ).to_dict(),
)


async def _is_approval_message(event: Event) -> bool:
    text = _event_plaintext(event)
    reply_message_id = _reply_message_id(event)
    return (
        parse_approval_command(
            text,
            has_reply_target=bool(reply_message_id),
            approval_prefix=get_contact_approval_config().approval_prefix,
        )
        is not None
    )


_request = on_request(priority=2, block=False)
_approval = on_message(Rule(_is_approval_message), priority=7, block=False)


@_request.handle()
async def handle_contact_request(bot: Bot, event: Event, matcher: Matcher) -> None:
    result = await handle_request_event(
        bot,
        event,
        config=get_contact_approval_config(),
    )
    if result.should_stop_propagation:
        matcher.stop_propagation()


@_approval.handle()
async def handle_contact_approval(bot: Bot, event: Event, matcher: Matcher) -> None:
    result = await handle_approval_message(
        bot,
        event,
        message_text=_event_plaintext(event),
        reply_message_id=_reply_message_id(event),
        config=get_contact_approval_config(),
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


def _reply_message_id(event: object) -> str | None:
    reply = getattr(event, "reply", None)
    if reply is None:
        return None
    value = getattr(reply, "message_id", None)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


__all__ = [
    "_approval",
    "_request",
    "handle_contact_approval",
    "handle_contact_request",
]
