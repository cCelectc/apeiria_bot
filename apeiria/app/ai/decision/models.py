"""Decision-layer models for reply engagement."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AIDecisionContext:
    """Minimal signals needed to decide whether AI should reply."""

    bot_self_id: str
    user_id: str
    message_text: str
    is_tome: bool
    is_private: bool


@dataclass(frozen=True)
class AIDecisionResult:
    """Decision result for one inbound event."""

    should_reply: bool
    reason: str
