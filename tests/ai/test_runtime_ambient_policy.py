# ruff: noqa: PLR2004

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from apeiria.app.ai.reply_strategy import WakeContext
from apeiria.app.ai.runtime.planning.hard_rules import decide_runtime_hard_rule
from apeiria.app.ai.runtime.session.context import RuntimeTurnSource
from apeiria.app.ai.runtime.session.runtime import (
    InMemoryAISessionRuntimeResolver,
    SessionRuntimePolicy,
)


def _now(second: int = 0) -> datetime:
    return datetime(2026, 4, 28, 12, 0, tzinfo=timezone.utc) + timedelta(seconds=second)


def _wake() -> WakeContext:
    return WakeContext(
        bot_self_id="bot-1",
        user_id="user-1",
        message_text="ambient",
        is_tome=False,
        is_private=False,
        is_future_task=False,
        allow_group_initiative=True,
    )


def _source(message_id: str, text: str = "ambient") -> RuntimeTurnSource:
    return RuntimeTurnSource(
        runtime_mode="message",
        message_text=text,
        source_message_id=message_id,
        user_id="user-1",
    )


def test_ambient_message_inside_merge_window_is_merged() -> None:
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
    assert decision.should_observe is True
    assert decision.should_reply is False
    assert decision.evidence["merged_message_count"] == 2
    assert runtime.pending_ambient_count == 2


def test_pending_ambient_merge_respects_max_pending_messages() -> None:
    runtime = InMemoryAISessionRuntimeResolver(
        policy=SessionRuntimePolicy(
            ambient_merge_window=timedelta(seconds=2),
            max_pending_messages=1,
        )
    ).resolve("session-1", now=_now())
    runtime.record_pending_ambient(_source("msg-1"), now=_now())

    decision = decide_runtime_hard_rule(
        wake_context=_wake(),
        source=_source("msg-2"),
        session_runtime=runtime,
        now=_now(1),
    )

    assert decision.action == "merge"
    assert decision.evidence["merged_message_count"] == 1
    assert decision.evidence["merged_message_ids"] == ("msg-2",)
    assert runtime.pending_ambient_count == 1


def test_ambient_cooldown_observes_without_reply() -> None:
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
    assert decision.should_observe is True
    assert decision.should_reply is False
    assert decision.evidence["cooldown_remaining_seconds"] == 120


def test_consecutive_ambient_reply_limit_observes_without_reply() -> None:
    runtime = InMemoryAISessionRuntimeResolver(
        policy=SessionRuntimePolicy(
            group_reply_cooldown=timedelta(seconds=0),
            max_consecutive_ambient_replies=1,
        )
    ).resolve("session-1", now=_now())
    runtime.record_ambient_reply(now=_now())

    decision = decide_runtime_hard_rule(
        wake_context=_wake(),
        source=_source("msg-2"),
        session_runtime=runtime,
        now=_now(1),
    )

    assert decision.action == "observe"
    assert decision.reason_codes == ("ambient_cooldown",)
    assert decision.evidence["consecutive_ambient_replies"] == 1


def test_direct_signal_bypasses_ambient_cooldown_budget() -> None:
    runtime = InMemoryAISessionRuntimeResolver(
        policy=SessionRuntimePolicy(group_reply_cooldown=timedelta(seconds=180))
    ).resolve("session-1", now=_now())
    runtime.record_ambient_reply(now=_now())
    wake = WakeContext(
        bot_self_id="bot-1",
        user_id="user-1",
        message_text="direct",
        is_tome=True,
        is_private=False,
        is_future_task=False,
        allow_group_initiative=True,
    )

    decision = decide_runtime_hard_rule(
        wake_context=wake,
        source=RuntimeTurnSource(
            runtime_mode="message",
            message_text="direct",
            source_message_id="msg-2",
            user_id="user-1",
            direct_signal=True,
        ),
        session_runtime=runtime,
        now=_now(10),
    )

    assert decision.action == "continue"
    assert decision.reason_codes == ("direct_signal",)
    assert decision.should_reply is True
