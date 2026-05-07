from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from apeiria.app.ai.runtime import AcceptedTurn, RuntimeInput
from apeiria.app.ai.runtime.session import (
    RuntimeSessionPolicy,
    RuntimeSessionStage,
    RuntimeSessionStore,
)


def test_runtime_session_stage_rejects_duplicate_event_keys() -> None:
    now = datetime(2026, 5, 6, tzinfo=timezone.utc)
    store = RuntimeSessionStore(
        policy=RuntimeSessionPolicy(duplicate_event_ttl=timedelta(seconds=30))
    )
    stage = RuntimeSessionStage(store=store, now=lambda: now)
    runtime_input = RuntimeInput(
        source_type="message",
        message_text="hello",
        session_id="session-1",
        user_id="user-1",
        sender_id="bot-1",
        dedupe_key="platform_message:1",
    )

    first = asyncio.run(stage.accept(runtime_input, trace_id="trace-1"))
    second = asyncio.run(stage.accept(runtime_input, trace_id="trace-2"))

    assert isinstance(first, AcceptedTurn)
    assert second is None
    assert first.diagnostics["session_decision"] == "accepted"


def test_runtime_session_stage_allows_duplicate_after_ttl() -> None:
    current = datetime(2026, 5, 6, tzinfo=timezone.utc)
    store = RuntimeSessionStore(
        policy=RuntimeSessionPolicy(duplicate_event_ttl=timedelta(seconds=30))
    )
    stage = RuntimeSessionStage(store=store, now=lambda: current)
    runtime_input = RuntimeInput(
        source_type="message",
        message_text="hello",
        session_id="session-1",
        user_id="user-1",
        sender_id="bot-1",
        dedupe_key="platform_message:1",
    )

    first = asyncio.run(stage.accept(runtime_input, trace_id="trace-1"))
    current = current + timedelta(seconds=31)
    second = asyncio.run(stage.accept(runtime_input, trace_id="trace-2"))

    assert first is not None
    assert second is not None
    assert second.turn_id == "trace-2"


def test_runtime_session_store_serializes_same_session_operations() -> None:
    async def run_operations() -> list[str]:
        store = RuntimeSessionStore()
        session = store.resolve("session-1")
        events: list[str] = []

        async def operation(name: str) -> str:
            events.append(f"start:{name}")
            await asyncio.sleep(0)
            events.append(f"end:{name}")
            return name

        await asyncio.gather(
            session.run_serialized(lambda: operation("a")),
            session.run_serialized(lambda: operation("b")),
        )
        return events

    events = asyncio.run(run_operations())

    assert events in (
        ["start:a", "end:a", "start:b", "end:b"],
        ["start:b", "end:b", "start:a", "end:a"],
    )


def test_runtime_session_records_merge_wait_and_defer_lifecycle_state() -> None:
    now = datetime(2026, 5, 6, tzinfo=timezone.utc)
    session = RuntimeSessionStore().resolve("session-1", now=now)
    runtime_input = RuntimeInput(
        source_type="message",
        message_text="hello",
        session_id="session-1",
        user_id="user-1",
        sender_id="bot-1",
        source_message_id="msg-1",
    )

    merge = session.record_pending_merge(runtime_input, reason="ambient_pending")
    session.record_wait(
        reason="short_pause",
        resume_at=now + timedelta(seconds=2),
        now=now,
    )
    session.record_defer(reason="active_turn", queued_at=now, now=now)

    assert merge.reason == "ambient_pending"
    assert merge.merged_message_ids == ("msg-1",)
    assert session.wait_state is not None
    assert session.wait_state.reason == "short_pause"
    assert session.defer_state is not None
    assert session.defer_state.reason == "active_turn"
