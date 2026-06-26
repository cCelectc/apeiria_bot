from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ContentSegment = tuple[str, str]
ContentKey = tuple[ContentSegment, ...]

SkipReason = Literal[
    "inactive_config",
    "not_group_message",
    "platform_disabled",
    "group_disallowed",
    "bot_message",
    "unsupported_message",
    "ignored_prefix",
    "same_user_duplicate",
    "below_threshold",
    "probability_not_met",
    "round_already_triggered",
]


@dataclass(frozen=True, slots=True)
class RepeaterEvent:
    platform: str | None
    group_id: str | None
    user_id: str | None
    bot_id: str | None
    message: object

    @property
    def group_scope(self) -> str | None:
        if self.platform is None or self.group_id is None:
            return None
        return f"{self.platform}:{self.group_id}"

    @property
    def is_bot_message(self) -> bool:
        return (
            self.user_id is not None
            and self.bot_id is not None
            and self.user_id == self.bot_id
        )


@dataclass(frozen=True, slots=True)
class RepeatRoundState:
    content_key: ContentKey
    message: object
    count: int
    last_user_id: str
    triggered: bool = False


@dataclass(frozen=True, slots=True)
class RepeatDecision:
    should_send: bool = False
    message: object | None = None
    probability: float | None = None
    reason: SkipReason | None = None
    group_scope: str | None = None


class RepeaterStateStore:
    """In-memory repeater state."""

    def __init__(self) -> None:
        self._states: dict[str, RepeatRoundState] = {}

    def get(self, group_scope: str) -> RepeatRoundState | None:
        return self._states.get(group_scope)

    def set(self, group_scope: str, state: RepeatRoundState) -> None:
        self._states[group_scope] = state

    def reset(self, group_scope: str) -> None:
        self._states.pop(group_scope, None)

    def clear(self) -> None:
        self._states.clear()


__all__ = [
    "ContentKey",
    "ContentSegment",
    "RepeatDecision",
    "RepeatRoundState",
    "RepeaterEvent",
    "RepeaterStateStore",
    "SkipReason",
]
