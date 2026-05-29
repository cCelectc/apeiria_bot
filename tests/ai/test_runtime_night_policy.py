from __future__ import annotations

from datetime import datetime, timedelta, timezone

from apeiria.ai.runtime_settings import AIRuntimeSettings
from apeiria.app.ai.reply_strategy.models import WakeContext
from apeiria.app.ai.runtime.planning.hard_rules import decide_runtime_hard_rule
from apeiria.app.ai.runtime.planning.night_policy import is_within_quiet_hours
from apeiria.app.ai.runtime.session.context import RuntimeTurnSource
from apeiria.app.ai.runtime.session.runtime import (
    InMemoryAISessionRuntime,
    InMemoryAISessionRuntimeResolver,
    SessionRuntimePolicy,
)

LOCAL_TZ = timezone(timedelta(hours=8))
UPDATED_QUIET_START_MINUTE = 30
UPDATED_QUIET_END_MINUTE = 300
UPDATED_AWAKE_LEASE_MINUTES = 9


def test_quiet_hours_helper_supports_cross_midnight_range() -> None:
    policy = SessionRuntimePolicy(
        quiet_hours_enabled=True,
        quiet_hours_start_minute=0,
        quiet_hours_end_minute=420,
    )

    assert is_within_quiet_hours(
        current_time=datetime(2026, 5, 29, 0, 15, tzinfo=LOCAL_TZ),
        policy=policy,
    )
    assert is_within_quiet_hours(
        current_time=datetime(2026, 5, 29, 6, 59, tzinfo=LOCAL_TZ),
        policy=policy,
    )
    assert not is_within_quiet_hours(
        current_time=datetime(2026, 5, 29, 7, 1, tzinfo=LOCAL_TZ),
        policy=policy,
    )


def test_session_awake_lease_expires_after_duration() -> None:
    runtime = InMemoryAISessionRuntime(
        session_id="session-1",
        policy=SessionRuntimePolicy(
            night_awake_lease=timedelta(minutes=5),
        ),
    )
    start = datetime(2026, 5, 29, 0, 0, tzinfo=timezone.utc)

    state = runtime.open_awake_lease(reason="direct_signal", now=start)

    assert state.lease_until == start + timedelta(minutes=5)
    assert runtime.has_active_awake_lease(now=start + timedelta(minutes=4, seconds=59))
    assert not runtime.has_active_awake_lease(now=start + timedelta(minutes=5))


def test_quiet_hours_ambient_group_message_is_observed() -> None:
    current_time = datetime(2026, 5, 29, 0, 30, tzinfo=LOCAL_TZ)
    runtime = InMemoryAISessionRuntime(
        session_id="session-1",
        policy=SessionRuntimePolicy(
            quiet_hours_enabled=True,
            quiet_hours_start_minute=0,
            quiet_hours_end_minute=420,
        ),
    )

    decision = decide_runtime_hard_rule(
        wake_context=_wake_context(),
        source=_source(),
        session_runtime=runtime,
        now=current_time,
    )

    assert decision.action == "observe"


def test_quiet_hours_direct_signal_opens_awake_lease() -> None:
    current_time = datetime(2026, 5, 29, 1, 0, tzinfo=LOCAL_TZ)
    runtime = InMemoryAISessionRuntime(
        session_id="session-1",
        policy=SessionRuntimePolicy(
            quiet_hours_enabled=True,
            quiet_hours_start_minute=0,
            quiet_hours_end_minute=420,
            night_awake_lease=timedelta(minutes=5),
        ),
    )

    decision = decide_runtime_hard_rule(
        wake_context=_wake_context(is_tome=True),
        source=_source(direct_signal=True),
        session_runtime=runtime,
        now=current_time,
    )

    assert decision.action == "continue"
    assert runtime.has_active_awake_lease(now=current_time + timedelta(minutes=4))


def test_active_awake_lease_keeps_session_responsive() -> None:
    current_time = datetime(2026, 5, 29, 1, 10, tzinfo=LOCAL_TZ)
    runtime = InMemoryAISessionRuntime(
        session_id="session-1",
        policy=SessionRuntimePolicy(
            quiet_hours_enabled=True,
            quiet_hours_start_minute=0,
            quiet_hours_end_minute=420,
            night_awake_lease=timedelta(minutes=5),
        ),
    )
    runtime.open_awake_lease(reason="direct_signal", now=current_time)

    decision = decide_runtime_hard_rule(
        wake_context=_wake_context(),
        source=_source(),
        session_runtime=runtime,
        now=current_time + timedelta(minutes=1),
    )

    assert decision.action == "continue"


def test_future_task_at_night_does_not_open_awake_lease() -> None:
    current_time = datetime(2026, 5, 29, 2, 0, tzinfo=LOCAL_TZ)
    runtime = InMemoryAISessionRuntime(
        session_id="session-1",
        policy=SessionRuntimePolicy(
            quiet_hours_enabled=True,
            quiet_hours_start_minute=0,
            quiet_hours_end_minute=420,
        ),
    )

    decision = decide_runtime_hard_rule(
        wake_context=_wake_context(is_future_task=True),
        source=_source(runtime_mode="future_task"),
        session_runtime=runtime,
        now=current_time,
    )

    assert decision.action == "continue"
    assert not runtime.has_active_awake_lease(now=current_time)


def test_reply_to_bot_breaks_through_quiet_hours() -> None:
    current_time = datetime(2026, 5, 29, 0, 45, tzinfo=LOCAL_TZ)
    runtime = InMemoryAISessionRuntime(
        session_id="session-1",
        policy=SessionRuntimePolicy(
            quiet_hours_enabled=True,
            quiet_hours_start_minute=0,
            quiet_hours_end_minute=420,
        ),
    )

    decision = decide_runtime_hard_rule(
        wake_context=_wake_context(),
        source=_source(reply_to_bot=True),
        session_runtime=runtime,
        now=current_time,
    )

    assert decision.action == "continue"


def test_quiet_hours_respects_direct_bypass_setting() -> None:
    current_time = datetime(2026, 5, 29, 1, 5, tzinfo=LOCAL_TZ)
    runtime = InMemoryAISessionRuntime(
        session_id="session-1",
        policy=SessionRuntimePolicy(
            quiet_hours_enabled=True,
            quiet_hours_start_minute=0,
            quiet_hours_end_minute=420,
            direct_bypass_ambient_budget=False,
        ),
    )

    decision = decide_runtime_hard_rule(
        wake_context=_wake_context(is_tome=True),
        source=_source(direct_signal=True),
        session_runtime=runtime,
        now=current_time,
    )

    assert decision.action == "observe"
    assert not runtime.has_active_awake_lease(now=current_time)


def test_session_resolver_updates_policy_from_latest_settings() -> None:
    runtime = InMemoryAISessionRuntimeResolver()
    now = datetime(2026, 5, 29, 12, 0, tzinfo=LOCAL_TZ)

    initial = runtime.resolve(
        "session-1",
        now=now,
        policy=SessionRuntimePolicy.from_settings(AIRuntimeSettings()),
    )
    assert initial.policy.quiet_hours_enabled is False

    updated = runtime.resolve(
        "session-1",
        now=now,
        policy=SessionRuntimePolicy.from_settings(
            AIRuntimeSettings(
                quiet_hours_enabled=True,
                quiet_hours_start_minute=UPDATED_QUIET_START_MINUTE,
                quiet_hours_end_minute=UPDATED_QUIET_END_MINUTE,
                night_awake_lease_minutes=UPDATED_AWAKE_LEASE_MINUTES,
            )
        ),
    )

    assert updated is initial
    assert updated.policy.quiet_hours_enabled is True
    assert updated.policy.night_awake_lease == timedelta(
        minutes=UPDATED_AWAKE_LEASE_MINUTES
    )


def _wake_context(
    *,
    is_tome: bool = False,
    is_private: bool = False,
    is_future_task: bool = False,
) -> WakeContext:
    return WakeContext(
        bot_self_id="bot-1",
        user_id="user-1",
        message_text="hello",
        is_tome=is_tome,
        is_private=is_private,
        is_future_task=is_future_task,
        allow_group_initiative=True,
    )


def _source(
    *,
    runtime_mode: str = "message",
    direct_signal: bool = False,
    is_private: bool = False,
    reply_to_bot: bool = False,
) -> RuntimeTurnSource:
    return RuntimeTurnSource(
        runtime_mode=runtime_mode,  # type: ignore[arg-type]
        message_text="hello",
        source_message_id="message-1",
        user_id="user-1",
        direct_signal=direct_signal,
        is_private=is_private,
        reply_to_bot=reply_to_bot,
    )
