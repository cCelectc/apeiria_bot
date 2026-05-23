from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from nonebot.log import logger

from apeiria.bot.platform import event_group_id, event_message_id, event_user_id

from .config import ContactOwnerConfig, get_contact_owner_config
from .providers import (
    ContactOwnerDeliveryResult,
    ContactOwnerProviderRegistry,
    contact_owner_provider_registry,
    parse_owner_target,
)

if TYPE_CHECKING:
    from nonebot.adapters import Bot, Event

ContactOwnerStatus = Literal[
    "ignored",
    "empty_message",
    "too_short",
    "owner_unconfigured",
    "invalid_owner_target",
    "unsupported_platform",
    "delivery_failed",
    "delivered",
]


@dataclass(frozen=True, slots=True)
class ContactOwnerHandleResult:
    status: ContactOwnerStatus
    reply: str | None = None
    should_stop_propagation: bool = False
    delivery_result: ContactOwnerDeliveryResult | None = None


def extract_contact_message_body(text: str, *, prefix: str) -> str | None:
    normalized = text.lstrip()
    if not normalized.startswith(prefix):
        return None
    return normalized[len(prefix) :].strip()


def is_contact_owner_trigger_text(text: str, *, prefix: str) -> bool:
    return extract_contact_message_body(text, prefix=prefix) is not None


async def handle_contact_owner_event(
    bot: "Bot",
    event: "Event",
    *,
    message_text: str,
    config: ContactOwnerConfig | None = None,
    registry: ContactOwnerProviderRegistry | None = None,
) -> ContactOwnerHandleResult:
    resolved_config = config or get_contact_owner_config()
    body = extract_contact_message_body(
        message_text,
        prefix=resolved_config.contact_prefix,
    )
    result = ContactOwnerHandleResult(status="ignored")
    if body is None:
        return result
    if not body:
        result = ContactOwnerHandleResult(
            status="empty_message",
            reply=resolved_config.empty_message_reply,
            should_stop_propagation=True,
        )
    elif len(body) <= resolved_config.minimum_message_length:
        result = ContactOwnerHandleResult(
            status="too_short",
            reply=resolved_config.too_short_reply,
            should_stop_propagation=True,
        )
    elif not resolved_config.owner_target:
        result = ContactOwnerHandleResult(
            status="owner_unconfigured",
            reply=resolved_config.owner_unconfigured_reply,
            should_stop_propagation=True,
        )
    else:
        result = await _deliver_contact_message(
            bot,
            event,
            body=body,
            config=resolved_config,
            registry=registry or contact_owner_provider_registry,
        )
    return result


async def _deliver_contact_message(
    bot: "Bot",
    event: "Event",
    *,
    body: str,
    config: ContactOwnerConfig,
    registry: ContactOwnerProviderRegistry,
) -> ContactOwnerHandleResult:
    target = parse_owner_target(config.owner_target)
    if target is None:
        return ContactOwnerHandleResult(
            status="invalid_owner_target",
            reply=config.invalid_owner_target_reply,
            should_stop_propagation=True,
        )

    provider = registry.resolve(bot, event, target)
    if provider is None:
        return ContactOwnerHandleResult(
            status="unsupported_platform",
            reply=config.unsupported_platform_reply,
            should_stop_propagation=True,
        )

    delivery_result = await provider.deliver_owner_message(
        bot,
        event,
        target,
        message=_format_owner_message(body, event),
    )
    if not delivery_result.success:
        logger.debug("Contact-owner delivery failed: {}", delivery_result.reason)
        return ContactOwnerHandleResult(
            status="delivery_failed",
            reply=config.delivery_failed_reply,
            should_stop_propagation=True,
            delivery_result=delivery_result,
        )
    return ContactOwnerHandleResult(
        status="delivered",
        reply=config.success_reply,
        should_stop_propagation=True,
        delivery_result=delivery_result,
    )


def _format_owner_message(body: str, event: "Event") -> str:
    lines = ["收到一条联系主人留言：", "", body, "", "来源："]
    user_id = event_user_id(event)
    if user_id is not None:
        lines.append(f"- 用户 ID：{user_id}")
    group_id = event_group_id(event)
    if group_id is not None:
        lines.append(f"- 群 ID：{group_id}")
    message_id = event_message_id(event)
    if message_id is not None:
        lines.append(f"- 消息 ID：{message_id}")
    if user_id is None and group_id is None and message_id is None:
        lines.append("- 未能获取来源 ID")
    return "\n".join(lines)


__all__ = [
    "ContactOwnerHandleResult",
    "ContactOwnerStatus",
    "extract_contact_message_body",
    "handle_contact_owner_event",
    "is_contact_owner_trigger_text",
]
