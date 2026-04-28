# ruff: noqa: PLR2004

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from apeiria.ai.config import AIPluginConfig
from apeiria.app.ai.session_runtime import (
    InMemoryAISessionRuntimeResolver,
    RuntimeTurnSource,
    SessionRuntimePolicy,
)


def _now(second: int = 0) -> datetime:
    return datetime(2026, 4, 28, 12, 0, second, tzinfo=timezone.utc)


def test_session_runtime_policy_uses_project_config_defaults() -> None:
    policy = SessionRuntimePolicy.from_config(AIPluginConfig())

    assert policy.ambient_merge_window == timedelta(milliseconds=1500)
    assert policy.max_pending_messages == 12
    assert policy.group_reply_cooldown == timedelta(seconds=180)
    assert policy.max_consecutive_ambient_replies == 1
    assert policy.direct_bypass_ambient_budget is True
    assert policy.duplicate_event_ttl == timedelta(seconds=30)


def test_resolver_reuses_session_runtime_and_cleans_idle_entries() -> None:
    resolver = InMemoryAISessionRuntimeResolver(
        policy=SessionRuntimePolicy(idle_ttl=timedelta(seconds=10))
    )

    runtime = resolver.resolve("session-1", now=_now())
    same_runtime = resolver.resolve("session-1", now=_now(5))
    other_runtime = resolver.resolve("session-2", now=_now(12))

    assert same_runtime is runtime
    assert other_runtime is not runtime
    assert resolver.session_count == 2

    removed = resolver.cleanup_idle(now=_now(16))

    assert removed == 1
    assert resolver.session_count == 1
    assert resolver.resolve("session-2", now=_now(16)) is other_runtime


def test_duplicate_event_ttl_tracks_and_expires_keys() -> None:
    runtime = InMemoryAISessionRuntimeResolver(
        policy=SessionRuntimePolicy(duplicate_event_ttl=timedelta(seconds=30))
    ).resolve("session-1", now=_now())

    assert runtime.record_event_if_new("message-1", now=_now()) is True
    assert runtime.record_event_if_new("message-1", now=_now(5)) is False
    assert runtime.record_event_if_new("message-1", now=_now(31)) is True


def test_pending_ambient_context_is_bounded_and_reports_merge_metadata() -> None:
    runtime = InMemoryAISessionRuntimeResolver(
        policy=SessionRuntimePolicy(max_pending_messages=2)
    ).resolve("session-1", now=_now())

    runtime.record_pending_ambient(
        RuntimeTurnSource(
            runtime_mode="message",
            message_text="first",
            source_message_id="msg-1",
            user_id="user-1",
        ),
        now=_now(),
    )
    runtime.record_pending_ambient(
        RuntimeTurnSource(
            runtime_mode="message",
            message_text="second",
            source_message_id="msg-2",
            user_id="user-2",
        ),
        now=_now(1),
    )
    merge = runtime.record_pending_ambient(
        RuntimeTurnSource(
            runtime_mode="message",
            message_text="third",
            source_message_id="msg-3",
            user_id="user-3",
        ),
        now=_now(2),
    )

    assert merge.merged_message_ids == ("msg-2", "msg-3")
    assert merge.merged_message_count == 2
    assert merge.reason == "ambient_pending_context"
    assert runtime.pending_ambient_count == 2


def test_wait_and_defer_metadata_are_recorded() -> None:
    runtime = InMemoryAISessionRuntimeResolver().resolve("session-1", now=_now())

    runtime.record_wait(reason="merge_window", resume_at=_now(2), now=_now())
    runtime.record_defer(reason="session_busy", queued_at=_now(1), now=_now(1))

    assert runtime.wait_state is not None
    assert runtime.wait_state.reason == "merge_window"
    assert runtime.wait_state.resume_at == _now(2)
    assert runtime.defer_state is not None
    assert runtime.defer_state.reason == "session_busy"
    assert runtime.defer_state.queued_at == _now(1)
