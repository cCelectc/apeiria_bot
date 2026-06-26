from __future__ import annotations

import time
from hashlib import sha256
from random import random
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .config import RepeaterConfig


class _RoundState:
    __slots__ = (
        "content_hash",
        "count",
        "last_triggered_at",
        "last_user_id",
        "message",
    )

    def __init__(
        self,
        content_hash: str,
        message: Any,
        count: int,
        last_user_id: str,
        last_triggered_at: float,
    ) -> None:
        self.content_hash = content_hash
        self.message = message
        self.count = count
        self.last_user_id = last_user_id
        self.last_triggered_at = last_triggered_at


def hash_message(message: Any) -> str:
    raw = str(message)
    return sha256(raw.encode("utf-8")).hexdigest()


class RepeaterService:
    def __init__(self) -> None:
        self._states: dict[str, _RoundState] = {}

    def evaluate(
        self,
        group_scope: str,
        content_hash: str,
        message: Any,
        user_id: str,
        *,
        config: RepeaterConfig,
    ) -> Any | None:
        now = time.monotonic()
        previous = self._states.get(group_scope)

        if previous is not None:
            if previous.content_hash != content_hash:
                previous = None
            elif previous.last_user_id == user_id:
                return None

        if previous is None:
            self._states[group_scope] = _RoundState(
                content_hash=content_hash,
                message=message,
                count=1,
                last_user_id=user_id,
                last_triggered_at=0.0,
            )
            return None

        count = previous.count + 1
        state = _RoundState(
            content_hash=content_hash,
            message=message,
            count=count,
            last_user_id=user_id,
            last_triggered_at=previous.last_triggered_at,
        )

        if count < config.repeat_threshold:
            self._states[group_scope] = state
            return None

        if now - previous.last_triggered_at < config.cooldown_seconds:
            self._states[group_scope] = state
            return None

        if random() >= config.probability:
            self._states[group_scope] = state
            return None

        self._states[group_scope] = _RoundState(
            content_hash=content_hash,
            message=message,
            count=count,
            last_user_id=user_id,
            last_triggered_at=now,
        )
        return message

    def reset(self, group_scope: str) -> None:
        self._states.pop(group_scope, None)


__all__ = ["RepeaterService", "hash_message"]
