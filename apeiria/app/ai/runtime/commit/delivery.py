"""Runtime reply delivery steps."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Protocol

from apeiria.ai.diagnostics import sanitize_runtime_diagnostic
from apeiria.app.ai.future_tasks.delivery_attempts import (
    AIDeliveryAttemptCreateInput,
    delivery_attempt_repository,
)

if TYPE_CHECKING:
    from apeiria.app.ai.runtime.session.context import RuntimeTurnInput


@dataclass(frozen=True)
class DeliveryRequest:
    """Provider-neutral proactive delivery request."""

    trace_id: str
    session_id: str
    runtime_mode: str
    bot_id: str
    platform: str
    scene_type: str
    scene_id: str
    message_text: str


@dataclass(frozen=True)
class PartialReplyDeliveryRequest:
    """Provider-neutral partial reply delivery request."""

    base: DeliveryRequest
    stream_id: str
    event_kind: str
    content_delta: str = ""
    diagnostic: str | None = None


@dataclass(frozen=True)
class DeliveryOutcome:
    """Outcome of a proactive message delivery."""

    delivered: bool
    error: str | None = None
    status: str | None = None
    reason: str | None = None
    channel: str | None = None
    remote_message_id: str | None = None

    def __post_init__(self) -> None:
        status = self.status or ("delivered" if self.delivered else "failed")
        reason = self.reason or (None if self.delivered else self.error)
        error = self.error or reason
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "error", error)


class DeliveryAdapter(Protocol):
    """Adapter boundary for proactive platform delivery."""

    supports_partial_replies: bool

    def can_deliver(self, request: DeliveryRequest) -> bool: ...

    async def deliver(self, request: DeliveryRequest) -> DeliveryOutcome: ...

    async def deliver_partial_reply(
        self,
        request: PartialReplyDeliveryRequest,
    ) -> DeliveryOutcome: ...


class DeliveryGateway:
    """Route proactive delivery requests to platform adapters."""

    def __init__(
        self,
        *,
        adapters: tuple[DeliveryAdapter, ...],
    ) -> None:
        self._adapters = adapters

    async def deliver(self, request: DeliveryRequest) -> DeliveryOutcome:
        for adapter in self._adapters:
            if adapter.can_deliver(request):
                return await adapter.deliver(request)
        return DeliveryOutcome(
            delivered=False,
            reason="delivery_adapter_unavailable",
        )

    def can_deliver_platform(self, platform: str) -> bool:
        """Return whether a proactive adapter is registered for a platform."""

        request = DeliveryRequest(
            trace_id="readiness",
            session_id="readiness",
            runtime_mode="future_task",
            bot_id="readiness",
            platform=platform,
            scene_type="private",
            scene_id="0",
            message_text="readiness",
        )
        return any(adapter.can_deliver(request) for adapter in self._adapters)

    def can_deliver_partial_replies(self, platform: str) -> bool:
        """Return whether an adapter claims partial-reply delivery support."""

        request = DeliveryRequest(
            trace_id="readiness",
            session_id="readiness",
            runtime_mode="message",
            bot_id="readiness",
            platform=platform,
            scene_type="private",
            scene_id="0",
            message_text="readiness",
        )
        return any(
            adapter.can_deliver(request) and adapter.supports_partial_replies
            for adapter in self._adapters
        )


class OneBotDeliveryAdapter:
    """Deliver proactive replies through the NoneBot OneBot API."""

    supports_partial_replies = False

    def can_deliver(self, request: DeliveryRequest) -> bool:
        return request.platform == "onebot"

    async def deliver_partial_reply(
        self,
        request: PartialReplyDeliveryRequest,
    ) -> DeliveryOutcome:
        _ = request
        return DeliveryOutcome(
            delivered=False,
            reason="partial_replies_unsupported",
            channel="onebot",
        )

    async def deliver(self, request: DeliveryRequest) -> DeliveryOutcome:
        bot = _get_nonebot_bots().get(request.bot_id)
        if bot is None:
            return DeliveryOutcome(
                delivered=False,
                reason="bot_not_connected",
                channel="onebot",
            )

        try:
            if request.scene_type == "group":
                response = await bot.call_api(
                    "send_group_msg",
                    group_id=int(request.scene_id),
                    message=request.message_text,
                )
            else:
                response = await bot.call_api(
                    "send_private_msg",
                    user_id=int(request.scene_id),
                    message=request.message_text,
                )
        except ValueError:
            return DeliveryOutcome(
                delivered=False,
                reason="invalid_scene_id",
                channel="onebot",
            )
        except Exception as exc:  # noqa: BLE001
            return DeliveryOutcome(
                delivered=False,
                error=_bounded_error(str(exc)),
                reason="adapter_error",
                channel="onebot",
            )

        return DeliveryOutcome(
            delivered=True,
            channel="onebot",
            remote_message_id=_remote_message_id(response),
        )


async def deliver_generated_reply(
    turn: "RuntimeTurnInput",
    reply_text: str,
    *,
    trace_id: str = "",
) -> DeliveryOutcome | None:
    """Deliver a proactive reply for future_task mode through the gateway."""
    if turn.runtime_mode != "future_task" or not reply_text.strip():
        return None

    delivery_request = DeliveryRequest(
        trace_id=trace_id,
        session_id=turn.identity.session_id,
        runtime_mode=turn.runtime_mode,
        bot_id=turn.identity.bot_id,
        platform=turn.identity.platform,
        scene_type=turn.identity.scene_type,
        scene_id=turn.identity.scene_id,
        message_text=reply_text,
    )
    future_task = turn.future_task
    if future_task is None:
        return await delivery_gateway.deliver(delivery_request)

    delivery_intent = _delivery_intent_for_task(future_task.task_id)
    delivered_attempt = await delivery_attempt_repository.get_delivered_attempt(
        task_id=future_task.task_id,
        delivery_intent=delivery_intent,
    )
    if delivered_attempt is not None:
        return DeliveryOutcome(
            delivered=True,
            status="delivered",
            reason="already_delivered",
            channel=delivered_attempt.channel,
            remote_message_id=delivered_attempt.remote_message_id,
        )

    attempt = await delivery_attempt_repository.create_or_reuse_pending(
        AIDeliveryAttemptCreateInput(
            task_id=future_task.task_id,
            trace_id=trace_id,
            session_id=turn.identity.session_id,
            delivery_intent=delivery_intent,
            platform=turn.identity.platform,
            scene_type=turn.identity.scene_type,
            scene_id=turn.identity.scene_id,
            message_preview=_message_preview(reply_text),
            message_hash=_message_hash(reply_text),
            created_at=_utcnow(),
        )
    )
    try:
        outcome = await delivery_gateway.deliver(delivery_request)
    except Exception as exc:  # noqa: BLE001
        error = _bounded_error(str(exc))
        await delivery_attempt_repository.mark_failed(
            attempt_id=attempt.attempt_id,
            reason="delivery_error",
            diagnostics={
                "error": error,
                "exception_type": type(exc).__name__,
            },
            failed_at=_utcnow(),
        )
        return DeliveryOutcome(
            delivered=False,
            error=error,
            reason="delivery_error",
        )

    if outcome.delivered:
        await delivery_attempt_repository.mark_delivered(
            attempt_id=attempt.attempt_id,
            channel=outcome.channel,
            remote_message_id=outcome.remote_message_id,
            delivered_at=_utcnow(),
        )
    else:
        await delivery_attempt_repository.mark_failed(
            attempt_id=attempt.attempt_id,
            reason=outcome.reason or outcome.error or "delivery_failed",
            diagnostics={
                "status": outcome.status,
                "reason": outcome.reason,
                "error": outcome.error,
                "channel": outcome.channel,
            },
            failed_at=_utcnow(),
        )
    return outcome


def _get_nonebot_bots() -> dict[str, Any]:
    import nonebot

    return dict(nonebot.get_bots())


def _remote_message_id(response: object) -> str | None:
    if isinstance(response, dict):
        value = response.get("message_id")
        if value is not None:
            return str(value)
    return None


def _bounded_error(error: str) -> str:
    sanitized = sanitize_runtime_diagnostic(error)
    if isinstance(sanitized, str) and sanitized:
        return sanitized
    return "adapter_error"


def _delivery_intent_for_task(task_id: str) -> str:
    return f"future_task:{task_id}:reply"


def _message_preview(message_text: str) -> str:
    return message_text.strip()[:200]


def _message_hash(message_text: str) -> str:
    return hashlib.sha256(message_text.encode("utf-8")).hexdigest()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


delivery_gateway = DeliveryGateway(adapters=(OneBotDeliveryAdapter(),))


__all__ = [
    "DeliveryAdapter",
    "DeliveryGateway",
    "DeliveryOutcome",
    "DeliveryRequest",
    "OneBotDeliveryAdapter",
    "PartialReplyDeliveryRequest",
    "deliver_generated_reply",
    "delivery_gateway",
]
