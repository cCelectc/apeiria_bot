from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Literal

import nonebot
from nonebot.log import logger

from .config import ContactApprovalConfig, OwnerTarget, parse_owner_target
from .models import (
    ApprovalActor,
    ApprovalCommand,
    ApprovalTicket,
    IncomingApprovalRequest,
    NotificationRef,
    parse_datetime,
    utcnow_text,
)

if TYPE_CHECKING:
    from nonebot.adapters import Bot, Event

    from .providers import (
        ContactApprovalProvider,
        ContactApprovalProviderRegistry,
    )
    from .store import ApprovalTicketStore

ContactApprovalStatus = Literal[
    "ignored",
    "unsupported",
    "disabled",
    "owner_unconfigured",
    "notified",
    "suppressed",
    "not_handled",
    "ticket_not_found",
    "missing_target",
    "unauthorized",
    "expired",
    "already_terminal",
    "approved",
    "rejected",
    "local_ignored",
    "detail",
    "listed",
    "platform_failed",
]


@dataclass(frozen=True, slots=True)
class ContactApprovalHandleResult:
    status: ContactApprovalStatus
    reply: str | None = None
    ticket: ApprovalTicket | None = None
    should_stop_propagation: bool = False


async def _handle_group_join_request(
    bot: "Bot",
    ticket: ApprovalTicket,
    *,
    config: ContactApprovalConfig,
    provider: ContactApprovalProvider,
    store: ApprovalTicketStore,
) -> ContactApprovalHandleResult:
    group_id = ticket.group_id
    if group_id is None or not _group_gate_allows(group_id, config):
        updated, _ = store.mark_terminal(
            ticket.ticket_id,
            status="suppressed",
            failure_reason="group_join_gate_suppressed",
        )
        should_stop = True
        if (
            updated is not None
            and config.suppressed_group_join_action == "reject"
            and group_id is not None
        ):
            await provider.reject_ticket(
                bot,
                updated,
                reason=config.suppressed_group_join_reject_reason,
            )
            should_stop = True
        return ContactApprovalHandleResult(
            status="suppressed",
            ticket=updated or ticket,
            should_stop_propagation=should_stop,
        )

    notification = await provider.send_group_notification(
        bot,
        group_id=group_id,
        message=_render_approval_card(ticket),
    )
    if not notification.success:
        updated, _ = store.mark_terminal(
            ticket.ticket_id,
            status="failed",
            failure_reason=notification.reason,
        )
        return ContactApprovalHandleResult(
            status="platform_failed",
            ticket=updated or ticket,
            should_stop_propagation=True,
        )
    if notification.message_id:
        ticket = (
            store.add_notification(
                ticket.ticket_id,
                NotificationRef(
                    scene_type="group",
                    scene_id=group_id,
                    message_id=notification.message_id,
                ),
            )
            or ticket
        )
    return ContactApprovalHandleResult(
        status="notified",
        ticket=ticket,
        should_stop_propagation=True,
    )


async def _notify_owners(
    bot: "Bot",
    ticket: ApprovalTicket,
    *,
    config: ContactApprovalConfig,
    provider: ContactApprovalProvider,
    store: ApprovalTicketStore,
) -> ContactApprovalHandleResult:
    owner_targets = _owner_targets(config)
    if not owner_targets:
        updated, _ = store.mark_terminal(
            ticket.ticket_id,
            status="failed",
            failure_reason="owner_unconfigured",
        )
        return ContactApprovalHandleResult(
            status="owner_unconfigured",
            ticket=updated or ticket,
            should_stop_propagation=True,
        )

    delivered = False
    for target in owner_targets:
        notification = await provider.send_owner_notification(
            bot,
            target,
            message=_render_approval_card(ticket),
        )
        if not notification.success:
            logger.debug(
                "Contact-approval owner notification failed: {}",
                notification.reason,
            )
            continue
        delivered = True
        if notification.message_id:
            ticket = (
                store.add_notification(
                    ticket.ticket_id,
                    NotificationRef(
                        scene_type="private",
                        scene_id=target.target_id,
                        message_id=notification.message_id,
                    ),
                )
                or ticket
            )

    if not delivered:
        updated, _ = store.mark_terminal(
            ticket.ticket_id,
            status="failed",
            failure_reason="owner_delivery_failed",
        )
        return ContactApprovalHandleResult(
            status="platform_failed",
            ticket=updated or ticket,
            should_stop_propagation=True,
        )
    return ContactApprovalHandleResult(
        status="notified",
        ticket=ticket,
        should_stop_propagation=True,
    )


async def _handle_ticket_command(  # noqa: PLR0911, PLR0913
    bot: "Bot",
    ticket: ApprovalTicket,
    *,
    command: ApprovalCommand,
    actor: ApprovalActor,
    config: ContactApprovalConfig,
    provider: ContactApprovalProvider,
    store: ApprovalTicketStore,
) -> ContactApprovalHandleResult:
    ticket, expired = store.mark_expired_if_needed(ticket)
    if expired:
        return ContactApprovalHandleResult(
            status="expired",
            reply=f"#{ticket.ticket_id} 已过期，请让对方重新申请。",
            ticket=ticket,
            should_stop_propagation=True,
        )
    if ticket.status != "pending":
        return ContactApprovalHandleResult(
            status="already_terminal",
            reply=_render_terminal_status(ticket),
            ticket=ticket,
            should_stop_propagation=True,
        )
    if not await _is_authorized(bot, ticket, actor=actor, provider=provider):
        return ContactApprovalHandleResult(
            status="unauthorized",
            reply=config.unauthorized_reply,
            ticket=ticket,
            should_stop_propagation=True,
        )
    if command.action == "detail":
        return ContactApprovalHandleResult(
            status="detail",
            reply=_render_ticket_detail(ticket),
            ticket=ticket,
            should_stop_propagation=True,
        )
    if command.action == "ignore":
        updated, _ = store.mark_terminal(
            ticket.ticket_id,
            status="ignored",
            handled_by=actor.user_id,
        )
        return ContactApprovalHandleResult(
            status="local_ignored",
            reply=f"#{ticket.ticket_id} 已忽略。",
            ticket=updated or ticket,
            should_stop_propagation=True,
        )
    target_status: Literal["approved", "rejected"]
    if command.action == "approve":
        action_result = await provider.approve_ticket(bot, ticket)
        target_status = "approved"
        reply = f"#{ticket.ticket_id} 已同意。"
    elif command.action == "reject":
        action_result = await provider.reject_ticket(
            bot,
            ticket,
            reason=command.reason,
        )
        target_status = "rejected"
        reply = f"#{ticket.ticket_id} 已拒绝。"
    else:
        return ContactApprovalHandleResult(status="not_handled")

    if not action_result.success:
        updated, _ = store.mark_terminal(
            ticket.ticket_id,
            status="failed",
            handled_by=actor.user_id,
            handled_reason=command.reason or None,
            failure_reason=action_result.reason,
        )
        return ContactApprovalHandleResult(
            status="platform_failed",
            reply=config.platform_failed_reply,
            ticket=updated or ticket,
            should_stop_propagation=True,
        )
    updated, _ = store.mark_terminal(
        ticket.ticket_id,
        status=target_status,
        handled_by=actor.user_id,
        handled_reason=command.reason or None,
    )
    return ContactApprovalHandleResult(
        status=target_status,
        reply=reply,
        ticket=updated or ticket,
        should_stop_propagation=True,
    )


async def _is_authorized(
    bot: "Bot",
    ticket: ApprovalTicket,
    *,
    actor: ApprovalActor,
    provider: ContactApprovalProvider,
) -> bool:
    if ticket.kind in {"friend_request", "bot_group_invite"}:
        return actor.scene_type == "private" and (actor.is_owner or actor.is_superuser)

    if ticket.kind != "group_join_request":
        return False
    if ticket.group_id is None:
        return False
    if actor.scene_type != "group" or actor.scene_id != ticket.group_id:
        return False
    if actor.is_owner or actor.is_superuser:
        return True
    result = await provider.is_group_operator(
        bot,
        group_id=ticket.group_id,
        user_id=actor.user_id,
    )
    return result.success


async def _list_pending(  # noqa: PLR0913
    bot: "Bot",
    event: "Event",
    store: ApprovalTicketStore,
    actor: ApprovalActor,
    *,
    config: ContactApprovalConfig,
    registry: ContactApprovalProviderRegistry,
) -> ContactApprovalHandleResult:
    if actor.scene_type == "private" and not (actor.is_owner or actor.is_superuser):
        return ContactApprovalHandleResult(
            status="unauthorized",
            reply=config.unauthorized_reply,
            should_stop_propagation=True,
        )
    if actor.scene_type == "group":
        authorized = actor.is_owner or actor.is_superuser
        if not authorized:
            provider = registry.resolve(bot, event)
            if provider is None:
                return ContactApprovalHandleResult(
                    status="unauthorized",
                    reply=config.unauthorized_reply,
                    should_stop_propagation=True,
                )
            authorized = await _is_group_list_authorized(
                bot,
                actor=actor,
                provider=provider,
            )
        if not authorized:
            return ContactApprovalHandleResult(
                status="unauthorized",
                reply=config.unauthorized_reply,
                should_stop_propagation=True,
            )
        tickets = store.list_pending(
            scene_type="group",
            scene_id=actor.scene_id,
            kinds={"group_join_request"},
        )
    else:
        tickets = store.list_pending(
            scene_type="private",
            scene_id=actor.scene_id,
            kinds={"friend_request", "bot_group_invite"},
        )
    if not tickets:
        reply = "当前没有待处理审批。"
    else:
        lines = [f"待处理审批 {len(tickets)} 个："]
        lines.extend(_render_ticket_list_item(ticket) for ticket in tickets[:20])
        reply = "\n".join(lines)
    return ContactApprovalHandleResult(
        status="listed",
        reply=reply,
        should_stop_propagation=True,
    )


async def _is_group_list_authorized(
    bot: "Bot",
    *,
    actor: ApprovalActor,
    provider: ContactApprovalProvider,
) -> bool:
    if actor.is_owner or actor.is_superuser:
        return True
    if actor.scene_type != "group":
        return False
    result = await provider.is_group_operator(
        bot,
        group_id=actor.scene_id,
        user_id=actor.user_id,
    )
    return result.success


def _resolve_ticket(
    store: ApprovalTicketStore,
    *,
    actor: ApprovalActor,
    command: ApprovalCommand,
    reply_message_id: str | None,
) -> ApprovalTicket | None:
    if command.ticket_id:
        return store.get(command.ticket_id)
    if reply_message_id is None:
        return None
    return store.get_by_notification(
        scene_type=actor.scene_type,
        scene_id=actor.scene_id,
        message_id=reply_message_id,
    )


def _request_kind_enabled(
    request: IncomingApprovalRequest,
    config: ContactApprovalConfig,
) -> bool:
    if request.kind == "friend_request":
        return config.friend_requests_enabled
    if request.kind == "bot_group_invite":
        return config.bot_group_invites_enabled
    if request.kind == "group_join_request":
        return config.group_join_requests_enabled
    return False


def _should_ignore_unscoped_scene_command(
    command: ApprovalCommand,
    *,
    actor: ApprovalActor,
    config: ContactApprovalConfig,
    reply_message_id: str | None,
) -> bool:
    if actor.scene_type == "private":
        return (
            not actor.is_owner
            and not actor.is_superuser
            and command.ticket_id is None
            and reply_message_id is None
        )
    if command.ticket_id is not None:
        return False
    if reply_message_id is not None:
        return False
    return not _group_gate_allows(actor.scene_id, config)


def _group_gate_allows(group_id: str, config: ContactApprovalConfig) -> bool:
    configured = set(config.group_join_gate_ids)
    if config.group_join_gate_mode == "blacklist":
        return group_id not in configured
    return group_id in configured


def _actor_from_event(
    event: "Event",
    *,
    config: ContactApprovalConfig,
) -> ApprovalActor | None:
    user_id = _event_user_id(event)
    if user_id is None:
        return None
    group_id = _string_attr(event, "group_id")
    scene_type = "group" if group_id is not None else "private"
    scene_id = group_id or user_id
    return ApprovalActor(
        user_id=user_id,
        scene_type=scene_type,
        scene_id=scene_id,
        is_owner=user_id in {target.target_id for target in _owner_targets(config)},
        is_superuser=user_id in _superuser_ids(),
    )


def _owner_targets(config: ContactApprovalConfig) -> tuple[OwnerTarget, ...]:
    if config.owner_targets:
        return config.owner_targets
    targets: list[OwnerTarget] = []
    seen: set[str] = set()
    for superuser in _superuser_ids():
        target = parse_owner_target(superuser)
        if target is None and superuser.isdecimal() and superuser != "0":
            target = OwnerTarget(scope="qq", target_id=superuser)
        if target is None or target.value in seen:
            continue
        seen.add(target.value)
        targets.append(target)
    return tuple(targets)


def _superuser_ids() -> set[str]:
    try:
        superusers = getattr(nonebot.get_driver().config, "superusers", set())
    except Exception:  # noqa: BLE001
        return set()
    values: set[str] = set()
    for item in superusers:
        text = str(item).strip()
        if not text:
            continue
        if ":" in text:
            _, text = text.rsplit(":", maxsplit=1)
        if text:
            values.add(text)
    return values


def _expires_at(config: ContactApprovalConfig) -> str:
    now = parse_datetime(utcnow_text())
    if now is None:
        return utcnow_text()
    return (now + timedelta(minutes=config.ticket_expiration_minutes)).isoformat(
        timespec="seconds"
    )


def _render_approval_card(ticket: ApprovalTicket) -> str:
    title_by_kind = {
        "friend_request": "好友审批",
        "bot_group_invite": "入群邀请",
        "group_join_request": "加群审批",
    }
    lines = [f"[{title_by_kind[ticket.kind]} #{ticket.ticket_id}] 待处理"]
    if ticket.group_id:
        group_label = (
            f"{ticket.group_name} / {ticket.group_id}"
            if ticket.group_name
            else ticket.group_id
        )
        lines.append(f"群：{group_label}")
    requester = (
        f"{ticket.nickname} / {ticket.user_id}" if ticket.nickname else ticket.user_id
    )
    user_label = "邀请人" if ticket.kind == "bot_group_invite" else "申请人"
    lines.append(f"{user_label}：{requester}")
    if ticket.comment:
        lines.append(f"验证信息：{ticket.comment}")
    lines.append(f"收到时间：{ticket.created_at}")
    if ticket.expires_at:
        lines.append(f"过期时间：{ticket.expires_at}")
    lines.append("")
    lines.append("操作：引用本消息回复 同意 / 拒绝 原因 / 忽略 / 详情")
    lines.append(
        f"也可发送：同意 #{ticket.ticket_id} / 拒绝 #{ticket.ticket_id} 原因 / "
        f"忽略 #{ticket.ticket_id} / 详情 #{ticket.ticket_id}"
    )
    return "\n".join(lines)


def _render_ticket_detail(ticket: ApprovalTicket) -> str:
    lines = [
        f"审批 #{ticket.ticket_id}",
        f"状态：{ticket.status}",
        f"类型：{ticket.kind}",
    ]
    if ticket.group_id:
        lines.append(f"群：{ticket.group_name or ticket.group_id} / {ticket.group_id}")
    user_label = "邀请人" if ticket.kind == "bot_group_invite" else "申请人"
    lines.append(
        f"{user_label}：{ticket.nickname or ticket.user_id} / {ticket.user_id}"
    )
    if ticket.comment:
        lines.append(f"验证信息：{ticket.comment}")
    lines.append(f"收到时间：{ticket.created_at}")
    if ticket.expires_at:
        lines.append(f"过期时间：{ticket.expires_at}")
    if ticket.handled_by:
        lines.append(f"处理人：{ticket.handled_by}")
    if ticket.handled_at:
        lines.append(f"处理时间：{ticket.handled_at}")
    if ticket.handled_reason:
        lines.append(f"处理原因：{ticket.handled_reason}")
    return "\n".join(lines)


def _render_terminal_status(ticket: ApprovalTicket) -> str:
    handler = f"，处理人：{ticket.handled_by}" if ticket.handled_by else ""
    return f"#{ticket.ticket_id} 已是 {ticket.status}{handler}。"


def _render_ticket_list_item(ticket: ApprovalTicket) -> str:
    label = ticket.nickname or ticket.user_id
    if ticket.kind != "friend_request" and ticket.group_id:
        label = f"{ticket.group_name or ticket.group_id} <- {label}"
    return f"#{ticket.ticket_id} {ticket.kind} {label} {ticket.created_at}"


def _event_user_id(event: object) -> str | None:
    getter = getattr(event, "get_user_id", None)
    if callable(getter):
        try:
            value = getter()
        except Exception:  # noqa: BLE001
            value = None
        if value is not None and str(value).strip():
            return str(value).strip()
    return _string_attr(event, "user_id")


def _string_attr(value: object, name: str) -> str | None:
    try:
        item = getattr(value, name, None)
    except Exception:  # noqa: BLE001
        return None
    if item is None:
        return None
    text = str(item).strip()
    return text or None
