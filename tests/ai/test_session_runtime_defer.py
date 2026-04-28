from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from apeiria.app.ai.reply_strategy import WakeContext
from apeiria.app.ai.session_runtime import (
    InMemoryAISessionRuntimeResolver,
    RuntimeTurnSource,
    decide_runtime_hard_rule,
)


def _now() -> datetime:
    return datetime(2026, 4, 28, 12, 0, tzinfo=timezone.utc)


def test_same_session_active_turn_defers_later_input() -> None:
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
            wake_context=WakeContext(
                bot_self_id="bot-1",
                user_id="user-1",
                message_text="direct",
                is_tome=True,
                is_private=False,
                is_future_task=False,
                allow_group_initiative=True,
            ),
            source=RuntimeTurnSource(
                runtime_mode="message",
                message_text="direct",
                source_message_id="msg-2",
                user_id="user-1",
                direct_signal=True,
            ),
            session_runtime=runtime,
            now=_now(),
        )

        release_first.set()
        await active_task
        return decision.action, decision.reason_codes

    assert asyncio.run(scenario()) == ("defer", ("session_busy",))
