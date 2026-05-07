"""Runtime session coordination stage."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, TypeVar

from apeiria.app.ai.runtime.entry import AcceptedTurn, RuntimeInput

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

ResultT = TypeVar("ResultT")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class RuntimeSessionPolicy:
    """In-memory session coordination policy."""

    duplicate_event_ttl: timedelta = timedelta(seconds=30)
    max_pending_messages: int = 12
    idle_ttl: timedelta = timedelta(minutes=5)


@dataclass(frozen=True, slots=True)
class RuntimeMergeState:
    """Metadata for source inputs merged into the current turn context."""

    merged_message_ids: tuple[str, ...] = ()
    merged_message_count: int = 0
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class RuntimePendingInput:
    """One buffered same-session source input."""

    source: RuntimeInput
    recorded_at: datetime


@dataclass(frozen=True, slots=True)
class RuntimeWaitState:
    """Metadata for a short resumable wait decision."""

    reason: str
    resume_at: datetime
    recorded_at: datetime


@dataclass(frozen=True, slots=True)
class RuntimeDeferState:
    """Metadata for a turn deferred behind active session work."""

    reason: str
    queued_at: datetime
    recorded_at: datetime


@dataclass(slots=True)
class RuntimeSession:
    """Mutable process-local coordination state for one AI session."""

    session_id: str
    policy: RuntimeSessionPolicy = field(default_factory=RuntimeSessionPolicy)
    last_active_at: datetime = field(default_factory=_utcnow)
    wait_state: RuntimeWaitState | None = None
    defer_state: RuntimeDeferState | None = None
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False, repr=False)
    _duplicate_events: dict[str, datetime] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )
    _pending_inputs: list[RuntimePendingInput] = field(
        default_factory=list,
        init=False,
        repr=False,
    )

    async def run_serialized(
        self,
        operation: Callable[[], Awaitable[ResultT]],
        *,
        now: datetime | None = None,
    ) -> ResultT:
        """Run an operation while holding this session's runtime lock."""

        async with self._lock:
            self.touch(now)
            return await operation()

    def record_event_if_new(self, event_key: str | None, *, now: datetime) -> bool:
        """Record a dedupe key and return false for a live duplicate."""

        if not event_key:
            self.touch(now)
            return True

        self._expire_duplicate_events(now)
        seen_at = self._duplicate_events.get(event_key)
        if seen_at is not None and now - seen_at <= self.policy.duplicate_event_ttl:
            self.touch(now)
            return False

        self._duplicate_events[event_key] = now
        self.touch(now)
        return True

    def record_pending_merge(
        self,
        source: RuntimeInput,
        *,
        reason: str,
        now: datetime | None = None,
    ) -> RuntimeMergeState:
        """Buffer source input for same-session merge accounting."""

        current_time = now or _utcnow()
        self._pending_inputs.append(
            RuntimePendingInput(source=source, recorded_at=current_time)
        )
        overflow = len(self._pending_inputs) - self.policy.max_pending_messages
        if overflow > 0:
            del self._pending_inputs[:overflow]

        self.touch(current_time)
        return RuntimeMergeState(
            merged_message_ids=tuple(
                pending.source.source_message_id
                for pending in self._pending_inputs
                if pending.source.source_message_id is not None
            ),
            merged_message_count=len(self._pending_inputs),
            reason=reason,
        )

    def record_wait(
        self,
        *,
        reason: str,
        resume_at: datetime,
        now: datetime,
    ) -> RuntimeWaitState:
        """Record metadata for a wait decision."""

        self.wait_state = RuntimeWaitState(
            reason=reason,
            resume_at=resume_at,
            recorded_at=now,
        )
        self.touch(now)
        return self.wait_state

    def record_defer(
        self,
        *,
        reason: str,
        queued_at: datetime,
        now: datetime,
    ) -> RuntimeDeferState:
        """Record metadata for a deferred turn."""

        self.defer_state = RuntimeDeferState(
            reason=reason,
            queued_at=queued_at,
            recorded_at=now,
        )
        self.touch(now)
        return self.defer_state

    def touch(self, now: datetime | None = None) -> None:
        """Refresh this session's last activity timestamp."""

        self.last_active_at = now or _utcnow()

    def is_idle_expired(self, *, now: datetime) -> bool:
        """Return whether this session can be evicted."""

        return (
            not self._lock.locked() and now - self.last_active_at > self.policy.idle_ttl
        )

    def _expire_duplicate_events(self, now: datetime) -> None:
        expired = [
            event_key
            for event_key, seen_at in self._duplicate_events.items()
            if now - seen_at > self.policy.duplicate_event_ttl
        ]
        for event_key in expired:
            del self._duplicate_events[event_key]


class RuntimeSessionStore:
    """Resolve process-local session coordination state."""

    def __init__(self, *, policy: RuntimeSessionPolicy | None = None) -> None:
        self._policy = policy or RuntimeSessionPolicy()
        self._sessions: dict[str, RuntimeSession] = {}

    @property
    def session_count(self) -> int:
        """Return retained session count."""

        return len(self._sessions)

    def resolve(
        self,
        session_id: str,
        *,
        now: datetime | None = None,
    ) -> RuntimeSession:
        """Return process-local coordination state for a session id."""

        current_time = now or _utcnow()
        self.evict_idle(now=current_time)
        session = self._sessions.get(session_id)
        if session is None:
            session = RuntimeSession(session_id=session_id, policy=self._policy)
            self._sessions[session_id] = session
        session.touch(current_time)
        return session

    def evict_idle(self, *, now: datetime | None = None) -> int:
        """Evict idle sessions and return the number removed."""

        current_time = now or _utcnow()
        expired = [
            session_id
            for session_id, session in self._sessions.items()
            if session.is_idle_expired(now=current_time)
        ]
        for session_id in expired:
            del self._sessions[session_id]
        return len(expired)


class RuntimeSessionStage:
    """Accept runtime inputs into a per-session turn lifecycle."""

    def __init__(
        self,
        *,
        store: RuntimeSessionStore | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._store = store or RuntimeSessionStore()
        self._now = now or _utcnow

    async def accept(
        self,
        runtime_input: RuntimeInput,
        *,
        trace_id: str,
    ) -> AcceptedTurn | None:
        """Apply duplicate protection and produce an accepted turn."""

        current_time = self._now()
        session = self._store.resolve(runtime_input.session_id, now=current_time)
        if not session.record_event_if_new(runtime_input.dedupe_key, now=current_time):
            return None
        return AcceptedTurn(
            turn_id=trace_id,
            input=runtime_input,
            lifecycle_state="accepted",
            accepted_at=current_time,
            diagnostics={"session_decision": "accepted"},
        )


__all__ = [
    "RuntimeDeferState",
    "RuntimeMergeState",
    "RuntimePendingInput",
    "RuntimeSession",
    "RuntimeSessionPolicy",
    "RuntimeSessionStage",
    "RuntimeSessionStore",
    "RuntimeWaitState",
]
