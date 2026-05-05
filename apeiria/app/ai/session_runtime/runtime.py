"""AI session runtime contracts and in-memory resolver."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable  # noqa: TC003
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Protocol, TypeVar, runtime_checkable

from apeiria.app.ai.agent_turn import AgentTurnResult

from .context import MergeMetadata, RuntimeTurnSource, TurnContext

if TYPE_CHECKING:
    from apeiria.ai.config import AIPluginConfig
    from apeiria.app.ai.session_runtime.runner import AgentRunner
    from apeiria.app.ai.session_runtime.stages import (
        RuntimeExecutionOutcome,
        RuntimeTurnPlan,
    )


ResultT = TypeVar("ResultT")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _current_task() -> asyncio.Task[object] | None:
    try:
        return asyncio.current_task()
    except RuntimeError:
        return None


@runtime_checkable
class AISessionRuntime(Protocol):
    """Protocol for session-scoped AI runtime coordinators."""

    session_id: str

    async def run_turn(
        self,
        context: TurnContext,
        plan: "RuntimeTurnPlan",
    ) -> "RuntimeExecutionOutcome":
        """Coordinate one AI turn inside the session boundary."""
        ...


@dataclass(frozen=True, slots=True)
class SessionRuntimePolicy:
    """Bounded in-memory session runtime policy."""

    ambient_merge_window: timedelta = timedelta(milliseconds=1500)
    max_pending_messages: int = 12
    group_reply_cooldown: timedelta = timedelta(seconds=180)
    max_consecutive_ambient_replies: int = 1
    direct_bypass_ambient_budget: bool = True
    duplicate_event_ttl: timedelta = timedelta(seconds=30)
    idle_ttl: timedelta = timedelta(minutes=5)

    @classmethod
    def from_config(cls, config: "AIPluginConfig") -> "SessionRuntimePolicy":
        """Build runtime policy from project AI plugin configuration."""

        return cls(
            ambient_merge_window=timedelta(milliseconds=config.ambient_merge_window_ms),
            max_pending_messages=config.max_pending_messages,
            group_reply_cooldown=timedelta(seconds=config.group_reply_cooldown_seconds),
            max_consecutive_ambient_replies=config.max_consecutive_ambient_replies,
            direct_bypass_ambient_budget=config.direct_bypass_ambient_budget,
            duplicate_event_ttl=timedelta(seconds=config.duplicate_event_ttl_seconds),
        )


@dataclass(frozen=True, slots=True)
class PendingAmbientMessage:
    """One ambient source buffered for a pending same-session turn."""

    source: RuntimeTurnSource
    recorded_at: datetime


@dataclass(frozen=True, slots=True)
class WaitState:
    """Metadata for a short resumable wait decision."""

    reason: str
    resume_at: datetime
    recorded_at: datetime


@dataclass(frozen=True, slots=True)
class DeferState:
    """Metadata for a turn deferred behind active session work."""

    reason: str
    queued_at: datetime
    recorded_at: datetime


@dataclass(slots=True)
class InMemoryAISessionRuntime:
    """In-memory runtime state for one AI session."""

    session_id: str
    policy: SessionRuntimePolicy = field(default_factory=SessionRuntimePolicy)
    runner: "AgentRunner | None" = None
    last_active_at: datetime = field(default_factory=_utcnow)
    wait_state: WaitState | None = None
    defer_state: DeferState | None = None
    last_ambient_reply_at: datetime | None = None
    consecutive_ambient_replies: int = 0
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False, repr=False)
    _active_turn_task: asyncio.Task[object] | None = field(
        default=None,
        init=False,
        repr=False,
    )
    _duplicate_events: dict[str, datetime] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )
    _pending_ambient: list[PendingAmbientMessage] = field(
        default_factory=list,
        init=False,
        repr=False,
    )

    async def run_turn(
        self,
        context: TurnContext,
        plan: "RuntimeTurnPlan",
    ) -> "RuntimeExecutionOutcome":
        """Serialize one runner invocation inside the session."""

        async def operation() -> "RuntimeExecutionOutcome":
            if self.runner is None:
                from apeiria.app.ai.session_runtime.stages import (
                    RuntimeExecutionOutcome,
                )

                return RuntimeExecutionOutcome(
                    stage="execution",
                    response=None,
                    skill_runtime=plan.skill_runtime,
                    post_tool_task_class=None,
                    delivery_result=None,
                    turn_result=AgentTurnResult.skipped(
                        trace_id=context.trace_id,
                        runtime_mode=context.runtime_mode,
                        finish_reason="no_runner",
                        diagnostic="No agent runner is configured for this session.",
                    ),
                )
            return await self.runner.run_turn(context, plan)

        return await self.run_serialized(operation, now=context.current_time)

    async def run_serialized(
        self,
        operation: Callable[[], Awaitable[ResultT]],
        *,
        now: datetime | None = None,
    ) -> ResultT:
        """Run one operation while holding the session turn lock."""

        current_time = now or _utcnow()
        async with self._lock:
            self._active_turn_task = _current_task()
            try:
                self.touch(current_time)
                return await operation()
            finally:
                self._active_turn_task = None

    @property
    def pending_ambient_count(self) -> int:
        """Return buffered ambient source count."""

        return len(self._pending_ambient)

    @property
    def is_active(self) -> bool:
        """Return whether a turn is currently running in this session."""

        return self._lock.locked()

    @property
    def current_turn_owns_lock(self) -> bool:
        """Return whether the calling task owns the active session turn lock."""

        if not self._lock.locked():
            return False
        current_task = _current_task()
        return current_task is not None and current_task is self._active_turn_task

    @property
    def has_other_active_turn(self) -> bool:
        """Return whether another task is running the active session turn."""

        return self.is_active and not self.current_turn_owns_lock

    def touch(self, now: datetime | None = None) -> None:
        """Refresh the runtime's last activity timestamp."""

        self.last_active_at = now or _utcnow()

    def record_event_if_new(self, event_key: str | None, *, now: datetime) -> bool:
        """Record an event key and return false when it is still a duplicate."""

        if not event_key:
            return True

        self._expire_duplicate_events(now)
        seen_at = self._duplicate_events.get(event_key)
        if seen_at is not None and now - seen_at <= self.policy.duplicate_event_ttl:
            self.touch(now)
            return False

        self._duplicate_events[event_key] = now
        self.touch(now)
        return True

    def record_pending_ambient(
        self,
        source: RuntimeTurnSource,
        *,
        now: datetime,
    ) -> MergeMetadata:
        """Buffer ambient input and return merge metadata for the current buffer."""

        self._pending_ambient.append(
            PendingAmbientMessage(source=source, recorded_at=now)
        )
        overflow = len(self._pending_ambient) - self.policy.max_pending_messages
        if overflow > 0:
            del self._pending_ambient[:overflow]

        self.touch(now)
        message_ids = tuple(
            item.source.source_message_id
            for item in self._pending_ambient
            if item.source.source_message_id is not None
        )
        return MergeMetadata(
            merged_message_ids=message_ids,
            merged_message_count=len(self._pending_ambient),
            reason="ambient_pending_context",
        )

    def should_merge_ambient(self, *, now: datetime) -> bool:
        """Return whether new ambient input should merge into pending context."""

        if not self._pending_ambient:
            return False
        last_pending = self._pending_ambient[-1]
        return now - last_pending.recorded_at <= self.policy.ambient_merge_window

    def record_ambient_reply(self, *, now: datetime) -> None:
        """Record that the bot emitted an ambient group-chat reply."""

        self.last_ambient_reply_at = now
        self.consecutive_ambient_replies += 1
        self.touch(now)

    def ambient_reply_block_evidence(self, *, now: datetime) -> dict[str, object]:
        """Return evidence when ambient reply budget blocks this turn."""

        if self.last_ambient_reply_at is not None:
            elapsed = now - self.last_ambient_reply_at
            remaining = self.policy.group_reply_cooldown - elapsed
            if remaining > timedelta(0):
                return {
                    "cooldown_remaining_seconds": int(remaining.total_seconds()),
                    "last_ambient_reply_at": self.last_ambient_reply_at.isoformat(),
                }

        if (
            self.consecutive_ambient_replies
            >= self.policy.max_consecutive_ambient_replies
        ):
            return {
                "consecutive_ambient_replies": self.consecutive_ambient_replies,
                "max_consecutive_ambient_replies": (
                    self.policy.max_consecutive_ambient_replies
                ),
            }

        return {}

    def record_wait(
        self,
        *,
        reason: str,
        resume_at: datetime,
        now: datetime,
    ) -> None:
        """Record metadata for a wait decision."""

        self.wait_state = WaitState(
            reason=reason,
            resume_at=resume_at,
            recorded_at=now,
        )
        self.touch(now)

    def record_defer(
        self,
        *,
        reason: str,
        queued_at: datetime,
        now: datetime,
    ) -> None:
        """Record metadata for a deferred turn."""

        self.defer_state = DeferState(
            reason=reason,
            queued_at=queued_at,
            recorded_at=now,
        )
        self.touch(now)

    def is_idle_expired(self, *, now: datetime) -> bool:
        """Return whether this runtime can be evicted from memory."""

        return not self.is_active and now - self.last_active_at > self.policy.idle_ttl

    def _expire_duplicate_events(self, now: datetime) -> None:
        expired = [
            event_key
            for event_key, seen_at in self._duplicate_events.items()
            if now - seen_at > self.policy.duplicate_event_ttl
        ]
        for event_key in expired:
            del self._duplicate_events[event_key]


class InMemoryAISessionRuntimeResolver:
    """Resolve and retain in-memory AI session runtimes."""

    def __init__(
        self,
        *,
        policy: SessionRuntimePolicy | None = None,
        runner: "AgentRunner | None" = None,
    ) -> None:
        self._policy = policy or SessionRuntimePolicy()
        self._runner = runner
        self._runtimes: dict[str, InMemoryAISessionRuntime] = {}

    @property
    def session_count(self) -> int:
        """Return number of retained session runtimes."""

        return len(self._runtimes)

    def resolve(
        self,
        session_id: str,
        *,
        now: datetime | None = None,
    ) -> InMemoryAISessionRuntime:
        """Resolve or create the in-memory runtime for one session."""

        current_time = now or _utcnow()
        runtime = self._runtimes.get(session_id)
        if runtime is None:
            runtime = InMemoryAISessionRuntime(
                session_id=session_id,
                policy=self._policy,
                runner=self._runner,
                last_active_at=current_time,
            )
            self._runtimes[session_id] = runtime
        else:
            runtime.touch(current_time)
        return runtime

    def cleanup_idle(self, *, now: datetime | None = None) -> int:
        """Evict idle session runtimes and return the number removed."""

        current_time = now or _utcnow()
        expired_session_ids = [
            session_id
            for session_id, runtime in self._runtimes.items()
            if runtime.is_idle_expired(now=current_time)
        ]
        for session_id in expired_session_ids:
            del self._runtimes[session_id]
        return len(expired_session_ids)
