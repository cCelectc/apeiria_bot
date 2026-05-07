from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from apeiria.app.ai.runtime.session.runtime import InMemoryAISessionRuntimeResolver


def _now() -> datetime:
    return datetime(2026, 4, 28, 12, 0, tzinfo=timezone.utc)


def test_same_session_operations_do_not_overlap() -> None:
    async def scenario() -> list[str]:
        runtime = InMemoryAISessionRuntimeResolver().resolve("session-1", now=_now())
        events: list[str] = []
        first_started = asyncio.Event()
        release_first = asyncio.Event()

        async def first_operation() -> str:
            events.append("first:start")
            first_started.set()
            await release_first.wait()
            events.append("first:end")
            return "first"

        async def second_operation() -> str:
            events.append("second:start")
            events.append("second:end")
            return "second"

        first_task = asyncio.create_task(
            runtime.run_serialized(first_operation, now=_now())
        )
        await first_started.wait()

        second_task = asyncio.create_task(
            runtime.run_serialized(second_operation, now=_now())
        )
        await asyncio.sleep(0)

        assert events == ["first:start"]

        release_first.set()
        await asyncio.gather(first_task, second_task)
        return events

    assert asyncio.run(scenario()) == [
        "first:start",
        "first:end",
        "second:start",
        "second:end",
    ]


def test_different_session_operations_are_not_globally_blocked() -> None:
    async def scenario() -> list[str]:
        resolver = InMemoryAISessionRuntimeResolver()
        first_runtime = resolver.resolve("session-1", now=_now())
        second_runtime = resolver.resolve("session-2", now=_now())
        events: list[str] = []
        first_started = asyncio.Event()
        second_finished = asyncio.Event()
        release_first = asyncio.Event()

        async def first_operation() -> str:
            events.append("first:start")
            first_started.set()
            await release_first.wait()
            events.append("first:end")
            return "first"

        async def second_operation() -> str:
            events.append("second:start")
            events.append("second:end")
            second_finished.set()
            return "second"

        first_task = asyncio.create_task(
            first_runtime.run_serialized(first_operation, now=_now())
        )
        await first_started.wait()

        second_task = asyncio.create_task(
            second_runtime.run_serialized(second_operation, now=_now())
        )
        await second_finished.wait()

        assert events == ["first:start", "second:start", "second:end"]

        release_first.set()
        await asyncio.gather(first_task, second_task)
        return events

    assert asyncio.run(scenario()) == [
        "first:start",
        "second:start",
        "second:end",
        "first:end",
    ]
