"""Application-level outbound message delivery models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from apeiria.app.ai.conversation.models import ScopeType

MessageDeliveryChannel = Literal["onebot.v11", "unsupported", "missing_bot"]


@dataclass(frozen=True)
class MessageDeliveryTarget:
    """Normalized outbound delivery target."""

    platform: str
    bot_id: str
    scope_type: ScopeType
    scope_id: str
    user_id: str | None


@dataclass(frozen=True)
class MessageDeliveryRequest:
    """One outbound delivery request."""

    target: MessageDeliveryTarget
    content_text: str


@dataclass(frozen=True)
class MessageDeliveryResult:
    """Result of one outbound delivery attempt."""

    delivered: bool
    channel: MessageDeliveryChannel
    error: str | None = None
    remote_message_id: str | None = None
