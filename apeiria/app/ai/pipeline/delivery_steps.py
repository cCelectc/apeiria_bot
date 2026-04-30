"""Runtime reply delivery steps."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from apeiria.app.ai.pipeline.service import AIRuntimeReplyRequest


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

    def can_deliver(self, request: DeliveryRequest) -> bool: ...

    async def deliver(self, request: DeliveryRequest) -> DeliveryOutcome: ...


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


class OneBotDeliveryAdapter:
    """Deliver proactive replies through the NoneBot OneBot API."""

    def can_deliver(self, request: DeliveryRequest) -> bool:
        return request.platform == "onebot"

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
    request: "AIRuntimeReplyRequest",
    reply_text: str,
    *,
    trace_id: str = "",
) -> DeliveryOutcome | None:
    """Deliver a proactive reply for future_task mode through the gateway."""
    if request.runtime_mode != "future_task" or not reply_text.strip():
        return None

    return await delivery_gateway.deliver(
        DeliveryRequest(
            trace_id=trace_id,
            session_id=request.identity.session_id,
            runtime_mode=request.runtime_mode,
            bot_id=request.identity.bot_id,
            platform=request.identity.platform,
            scene_type=request.identity.scene_type,
            scene_id=request.identity.scene_id,
            message_text=reply_text,
        )
    )


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
    return error[:200] if error else "adapter_error"


delivery_gateway = DeliveryGateway(adapters=(OneBotDeliveryAdapter(),))


__all__ = [
    "DeliveryAdapter",
    "DeliveryGateway",
    "DeliveryOutcome",
    "DeliveryRequest",
    "OneBotDeliveryAdapter",
    "deliver_generated_reply",
    "delivery_gateway",
]
