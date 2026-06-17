from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from nonebot.log import logger

from apeiria.bot.superuser import is_superuser_id

from .config import SelfRevokeConfig, get_self_revoke_config
from .providers import (
    FeedbackKind,
    RevokeActionResult,
    SelfRevokeProvider,
    SelfRevokeProviderRegistry,
    self_revoke_provider_registry,
)

if TYPE_CHECKING:
    from nonebot.adapters import Bot, Event

SelfRevokeStatus = Literal[
    "no_provider",
    "no_reply_target",
    "permission_denied",
    "not_bot_authored",
    "target_revoke_failed",
    "target_revoked",
]


@dataclass(frozen=True, slots=True)
class SelfRevokeHandleResult:
    """Outcome returned by the self-revoke handler core."""

    status: SelfRevokeStatus
    target_revoked: bool = False
    should_stop_propagation: bool = False
    feedback_result: RevokeActionResult | None = None
    trigger_revoke_result: RevokeActionResult | None = None


TRIGGER_TEXTS = frozenset({"撤回", "revoke"})


def is_revoke_trigger_text(text: str) -> bool:
    return text.strip().lower() in TRIGGER_TEXTS


def is_superuser_event(bot: "Bot", event: "Event") -> bool:
    try:
        user_id = str(event.get_user_id())
    except Exception:  # noqa: BLE001
        return False

    adapter_name = ""
    with suppress(Exception):
        adapter_name = bot.adapter.get_name().split(maxsplit=1)[0].lower()

    return is_superuser_id(user_id, adapter_prefix=adapter_name)


async def handle_self_revoke_event(
    bot: "Bot",
    event: "Event",
    *,
    config: SelfRevokeConfig | None = None,
    registry: SelfRevokeProviderRegistry | None = None,
) -> SelfRevokeHandleResult:
    resolved_config = config or get_self_revoke_config()
    resolved_registry = registry or self_revoke_provider_registry
    provider = resolved_registry.resolve(bot, event)
    if provider is None:
        return SelfRevokeHandleResult(status="no_provider")

    target = await provider.get_reply_target(bot, event)
    if target is None:
        return SelfRevokeHandleResult(status="no_reply_target")

    if resolved_config.permission == "superuser" and not is_superuser_event(
        bot,
        event,
    ):
        feedback_result = await _maybe_apply_feedback(
            provider,
            bot,
            event,
            config=resolved_config,
            kind="failure",
        )
        return SelfRevokeHandleResult(
            status="permission_denied",
            should_stop_propagation=True,
            feedback_result=feedback_result,
        )

    if not await provider.is_bot_authored(bot, event, target):
        feedback_result = await _maybe_apply_feedback(
            provider,
            bot,
            event,
            config=resolved_config,
            kind="failure",
        )
        return SelfRevokeHandleResult(
            status="not_bot_authored",
            should_stop_propagation=True,
            feedback_result=feedback_result,
        )

    revoke_result = await provider.revoke_message(bot, event, target)
    if not revoke_result.success:
        logger.debug("Self-revoke target revoke failed: {}", revoke_result.reason)
        feedback_result = await _maybe_apply_feedback(
            provider,
            bot,
            event,
            config=resolved_config,
            kind="failure",
        )
        return SelfRevokeHandleResult(
            status="target_revoke_failed",
            should_stop_propagation=True,
            feedback_result=feedback_result,
        )

    trigger_revoke_result: RevokeActionResult | None = None
    if resolved_config.revoke_trigger_message:
        trigger_revoke_result = await provider.revoke_trigger_message(bot, event)
        if not trigger_revoke_result.success:
            logger.debug(
                "Self-revoke trigger-message revoke failed: {}",
                trigger_revoke_result.reason,
            )
    feedback_result = None
    if not resolved_config.revoke_trigger_message:
        feedback_result = await _maybe_apply_feedback(
            provider,
            bot,
            event,
            config=resolved_config,
            kind="success",
        )
    return SelfRevokeHandleResult(
        status="target_revoked",
        target_revoked=True,
        should_stop_propagation=True,
        feedback_result=feedback_result,
        trigger_revoke_result=trigger_revoke_result,
    )


async def _maybe_apply_feedback(
    provider: SelfRevokeProvider,
    bot: "Bot",
    event: "Event",
    *,
    config: SelfRevokeConfig,
    kind: FeedbackKind,
) -> RevokeActionResult | None:
    if config.feedback != "reaction":
        return None
    return await provider.apply_feedback(bot, event, kind=kind)


__all__ = [
    "TRIGGER_TEXTS",
    "SelfRevokeHandleResult",
    "handle_self_revoke_event",
    "is_revoke_trigger_text",
    "is_superuser_event",
]
