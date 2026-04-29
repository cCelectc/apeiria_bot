# ruff: noqa: PLR2004

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from apeiria.app.ai.reply_strategy import WakeContext
from apeiria.app.ai.session_runtime import (
    InMemoryAISessionRuntimeResolver,
    RuntimeTurnSource,
    SessionRuntimePolicy,
    decide_runtime_hard_rule,
)


def _now(second: int = 0) -> datetime:
    return datetime(2026, 4, 28, 12, 0, tzinfo=timezone.utc) + timedelta(seconds=second)


def _wake(
    *,
    message_text: str = "ambient",
    is_tome: bool = False,
) -> WakeContext:
    return WakeContext(
        bot_self_id="bot-1",
        user_id="user-1",
        message_text=message_text,
        is_tome=is_tome,
        is_private=False,
        is_future_task=False,
        allow_group_initiative=True,
    )


def _source(
    message_id: str,
    *,
    message_text: str = "ambient",
    direct_signal: bool = False,
) -> RuntimeTurnSource:
    return RuntimeTurnSource(
        runtime_mode="message",
        message_text=message_text,
        source_message_id=message_id,
        user_id="user-1",
        direct_signal=direct_signal,
    )


def test_later_same_session_ambient_input_merges_into_pending_context() -> None:
    runtime = InMemoryAISessionRuntimeResolver(
        policy=SessionRuntimePolicy(ambient_merge_window=timedelta(seconds=2))
    ).resolve("session-1", now=_now())
    runtime.record_pending_ambient(_source("msg-1"), now=_now())

    decision = decide_runtime_hard_rule(
        wake_context=_wake(),
        source=_source("msg-2"),
        session_runtime=runtime,
        now=_now(1),
    )

    assert decision.action == "merge"
    assert decision.reason_codes == ("ambient_merge_window",)
    assert decision.evidence["merged_message_ids"] == ("msg-1", "msg-2")
    assert decision.should_observe is True
    assert decision.should_reply is False


def test_later_same_session_direct_input_defers_behind_active_turn() -> None:
    async def scenario() -> tuple[str, tuple[str, ...]]:
        runtime = InMemoryAISessionRuntimeResolver().resolve("session-1", now=_now())
        first_started = asyncio.Event()
        release_first = asyncio.Event()

        async def active_operation() -> None:
            first_started.set()
            await release_first.wait()

        active_task = asyncio.create_task(
            runtime.run_serialized(active_operation, now=_now())
        )
        await first_started.wait()

        decision = decide_runtime_hard_rule(
            wake_context=_wake(message_text="direct", is_tome=True),
            source=_source("msg-2", message_text="direct", direct_signal=True),
            session_runtime=runtime,
            now=_now(1),
        )

        release_first.set()
        await active_task
        return decision.action, decision.reason_codes

    assert asyncio.run(scenario()) == ("defer", ("session_busy",))


def test_later_same_session_ambient_input_observes_during_cooldown() -> None:
    runtime = InMemoryAISessionRuntimeResolver(
        policy=SessionRuntimePolicy(group_reply_cooldown=timedelta(seconds=180))
    ).resolve("session-1", now=_now())
    runtime.record_ambient_reply(now=_now())

    decision = decide_runtime_hard_rule(
        wake_context=_wake(),
        source=_source("msg-2"),
        session_runtime=runtime,
        now=_now(60),
    )

    assert decision.action == "observe"
    assert decision.reason_codes == ("ambient_cooldown",)
    assert decision.evidence["cooldown_remaining_seconds"] == 120
    assert decision.should_observe is True
    assert decision.should_reply is False


def test_later_same_session_duplicate_input_drops_before_observation() -> None:
    runtime = InMemoryAISessionRuntimeResolver().resolve("session-1", now=_now())
    wake = _wake(message_text="direct", is_tome=True)
    source = _source("msg-1", message_text="direct", direct_signal=True)

    first = decide_runtime_hard_rule(
        wake_context=wake,
        source=source,
        session_runtime=runtime,
        now=_now(),
    )
    duplicate = decide_runtime_hard_rule(
        wake_context=wake,
        source=source,
        session_runtime=runtime,
        now=_now(1),
    )

    assert first.action == "continue"
    assert duplicate.action == "drop"
    assert duplicate.reason_codes == ("duplicate_event",)
    assert duplicate.should_observe is False
    assert duplicate.should_reply is False
