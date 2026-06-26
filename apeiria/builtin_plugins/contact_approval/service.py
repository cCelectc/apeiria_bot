from __future__ import annotations

from typing import TYPE_CHECKING

from .commands import parse_approval_command
from .config import ContactApprovalConfig, get_contact_approval_config
from .providers import (
    ContactApprovalProviderRegistry,
    contact_approval_provider_registry,
)
from .store import ApprovalTicketStore, approval_ticket_store
from .workflow import (
    ContactApprovalHandleResult,
    ContactApprovalStatus,
    _actor_from_event,
    _expires_at,
    _handle_group_join_request,
    _handle_ticket_command,
    _list_pending,
    _notify_owners,
    _request_kind_enabled,
    _resolve_ticket,
    _should_ignore_unscoped_scene_command,
)

if TYPE_CHECKING:
    from nonebot.adapters import Bot, Event


async def handle_request_event(
    bot: "Bot",
    event: "Event",
    *,
    config: ContactApprovalConfig | None = None,
    registry: ContactApprovalProviderRegistry | None = None,
    store: ApprovalTicketStore | None = None,
) -> ContactApprovalHandleResult:
    resolved_config = config or get_contact_approval_config()
    resolved_registry = registry or contact_approval_provider_registry
    resolved_store = store or approval_ticket_store
    provider = resolved_registry.resolve(bot, event)
    if provider is None:
        return ContactApprovalHandleResult(status="unsupported")

    request = await provider.normalize_request(bot, event)
    if request is None:
        return ContactApprovalHandleResult(status="ignored")
    if not _request_kind_enabled(request, resolved_config):
        return ContactApprovalHandleResult(status="disabled")

    ticket = resolved_store.upsert_pending(
        request,
        expires_at=_expires_at(resolved_config),
    )
    if request.kind == "group_join_request":
        return await _handle_group_join_request(
            bot,
            ticket,
            config=resolved_config,
            provider=provider,
            store=resolved_store,
        )
    return await _notify_owners(
        bot,
        ticket,
        config=resolved_config,
        provider=provider,
        store=resolved_store,
    )


async def handle_approval_message(  # noqa: PLR0911, PLR0913
    bot: "Bot",
    event: "Event",
    *,
    message_text: str,
    reply_message_id: str | None = None,
    config: ContactApprovalConfig | None = None,
    registry: ContactApprovalProviderRegistry | None = None,
    store: ApprovalTicketStore | None = None,
) -> ContactApprovalHandleResult:
    resolved_config = config or get_contact_approval_config()
    command = parse_approval_command(
        message_text,
        has_reply_target=bool(reply_message_id),
        approval_prefix=resolved_config.approval_prefix,
    )
    if command is None:
        return ContactApprovalHandleResult(status="not_handled")

    actor = _actor_from_event(event, config=resolved_config)
    if actor is None:
        return ContactApprovalHandleResult(status="not_handled")

    resolved_store = store or approval_ticket_store
    if _should_ignore_unscoped_scene_command(
        command,
        actor=actor,
        config=resolved_config,
        reply_message_id=reply_message_id,
    ):
        return ContactApprovalHandleResult(status="not_handled")

    if command.action == "list":
        return await _list_pending(
            bot,
            event,
            resolved_store,
            actor,
            config=resolved_config,
            registry=registry or contact_approval_provider_registry,
        )
    if command.missing_target:
        return ContactApprovalHandleResult(
            status="missing_target",
            reply=resolved_config.missing_target_reply,
            should_stop_propagation=True,
        )

    ticket = _resolve_ticket(
        resolved_store,
        actor=actor,
        command=command,
        reply_message_id=reply_message_id,
    )
    if ticket is None:
        return ContactApprovalHandleResult(
            status="ticket_not_found",
            reply=resolved_config.ticket_not_found_reply,
            should_stop_propagation=True,
        )

    provider = (registry or contact_approval_provider_registry).resolve(bot, event)
    if provider is None:
        return ContactApprovalHandleResult(
            status="unsupported",
            reply=resolved_config.platform_failed_reply,
            ticket=ticket,
            should_stop_propagation=True,
        )
    return await _handle_ticket_command(
        bot,
        ticket,
        command=command,
        actor=actor,
        config=resolved_config,
        provider=provider,
        store=resolved_store,
    )


__all__ = [
    "ContactApprovalHandleResult",
    "ContactApprovalStatus",
    "handle_approval_message",
    "handle_request_event",
]
