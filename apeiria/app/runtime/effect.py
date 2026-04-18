"""Formal Effect objects and the runtime-scoped effect queue.

`Effect` is the Runtime Kernel's unified output semantics. Reply, proactive
send, model invocation, tool execution, diagnostics, and deferred schedules
all enter the runtime as effects. The queue on `RuntimeFrame` gives ordering,
attribution, and audit to every side effect the kernel produces.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

EffectKind = Literal[
    "reply",
    "send",
    "model_request",
    "tool_call",
    "diagnostic",
    "schedule",
]

EffectBucket = Literal[
    "immediate",
    "message_send",
    "post_send",
    "deferred",
]

EffectStatus = Literal["pending", "flushed", "failed", "dropped"]

_DEFAULT_BUCKET: dict[EffectKind, EffectBucket] = {
    "reply": "message_send",
    "send": "message_send",
    "model_request": "immediate",
    "tool_call": "immediate",
    "diagnostic": "immediate",
    "schedule": "deferred",
}


@dataclass
class Effect:
    """One structured runtime output."""

    effect_id: str
    kind: EffectKind
    bucket: EffectBucket
    origin: str
    created_at: datetime
    request_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    status: EffectStatus = "pending"
    ordinal: int = 0
    result: Any = None
    error: str | None = None
    flushed_at: datetime | None = None

    def mark_flushed(self, result: Any = None) -> None:
        self.status = "flushed"
        self.result = result
        self.flushed_at = datetime.now(timezone.utc)

    def mark_failed(self, error: str) -> None:
        self.status = "failed"
        self.error = error
        self.flushed_at = datetime.now(timezone.utc)

    def mark_dropped(self, reason: str) -> None:
        self.status = "dropped"
        self.error = reason
        self.flushed_at = datetime.now(timezone.utc)


def new_effect(
    *,
    kind: EffectKind,
    origin: str,
    request_id: str | None = None,
    bucket: EffectBucket | None = None,
    payload: dict[str, Any] | None = None,
) -> Effect:
    """Build a fresh pending effect with a default bucket for its kind."""

    return Effect(
        effect_id=f"eff_{uuid4().hex}",
        kind=kind,
        bucket=bucket or _DEFAULT_BUCKET[kind],
        origin=origin,
        created_at=datetime.now(timezone.utc),
        request_id=request_id,
        payload=dict(payload or {}),
    )


class EffectQueue:
    """Append-only effect log bound to a runtime frame."""

    def __init__(self) -> None:
        self._effects: list[Effect] = []

    def enqueue(self, effect: Effect) -> Effect:
        effect.ordinal = len(self._effects) + 1
        self._effects.append(effect)
        return effect

    def snapshot(self) -> tuple[Effect, ...]:
        return tuple(self._effects)

    def by_kind(self, kind: EffectKind) -> tuple[Effect, ...]:
        return tuple(effect for effect in self._effects if effect.kind == kind)

    def by_bucket(self, bucket: EffectBucket) -> tuple[Effect, ...]:
        return tuple(effect for effect in self._effects if effect.bucket == bucket)

    def clear(self) -> None:
        self._effects.clear()

    def __len__(self) -> int:
        return len(self._effects)


_current_queue: ContextVar[EffectQueue | None] = ContextVar(
    "apeiria_runtime_effect_queue",
    default=None,
)


def current_effect_queue() -> EffectQueue | None:
    """Return the active effect queue, if any is bound to this context."""

    return _current_queue.get()


def bind_effect_queue(queue: EffectQueue) -> Any:
    """Bind ``queue`` to the current context; returns a reset token."""

    return _current_queue.set(queue)


def reset_effect_queue(token: Any) -> None:
    """Reset the effect-queue binding using the token from ``bind_effect_queue``."""

    _current_queue.reset(token)
