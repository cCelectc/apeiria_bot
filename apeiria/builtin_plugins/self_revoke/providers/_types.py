from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol

if TYPE_CHECKING:
    from nonebot.adapters import Bot, Event

from apeiria.bot.platform import ActionResult, ProviderRegistry

FeedbackKind = Literal["success", "failure"]


@dataclass(frozen=True, slots=True)
class RevokeTarget:
    """Provider-neutral reference to one platform message."""

    message_id: str
    author_id: str | None = None


@dataclass(frozen=True, slots=True)
class RevokeActionResult(ActionResult):
    """Result for best-effort platform operations."""

    @classmethod
    def failed(cls, reason: str = "operation_failed") -> "RevokeActionResult":
        return cls(status="failed", reason=reason)


class SelfRevokeProvider(Protocol):
    """Adapter capability boundary consumed by the self-revoke plugin."""

    def supports(self, bot: "Bot", event: "Event") -> bool: ...

    async def get_reply_target(
        self,
        bot: "Bot",
        event: "Event",
    ) -> RevokeTarget | None: ...

    async def is_bot_authored(
        self,
        bot: "Bot",
        event: "Event",
        target: RevokeTarget,
    ) -> bool: ...

    async def revoke_message(
        self,
        bot: "Bot",
        event: "Event",
        target: RevokeTarget,
    ) -> RevokeActionResult: ...

    async def revoke_trigger_message(
        self,
        bot: "Bot",
        event: "Event",
    ) -> RevokeActionResult: ...

    async def apply_feedback(
        self,
        bot: "Bot",
        event: "Event",
        *,
        kind: FeedbackKind,
    ) -> RevokeActionResult: ...


class SelfRevokeProviderRegistry(ProviderRegistry["SelfRevokeProvider"]):
    """Resolve the first provider that supports a bot/event pair."""

    def __init__(self, providers: tuple[SelfRevokeProvider, ...]) -> None:
        super().__init__(providers, label="Self-revoke provider")
