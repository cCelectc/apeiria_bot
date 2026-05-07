from __future__ import annotations

from datetime import datetime, timezone

import pytest

from apeiria.app.ai.reply_strategy import WakeContext
from apeiria.app.ai.runtime.planning.hard_rules import decide_runtime_hard_rule
from apeiria.app.ai.runtime.session.context import RuntimeTurnSource
from apeiria.app.ai.runtime.session.runtime import InMemoryAISessionRuntimeResolver
from apeiria.app.ai.runtime.strategy import RuntimeHardRuleDecision


def _now() -> datetime:
    return datetime(2026, 4, 28, 12, 0, tzinfo=timezone.utc)


def _source(
    *,
    message_text: str = "hello",
    message_id: str | None = "msg-1",
    runtime_mode: str = "message",
    direct_signal: bool = False,
    is_private: bool = False,
) -> RuntimeTurnSource:
    return RuntimeTurnSource(
        runtime_mode=runtime_mode,  # type: ignore[arg-type]
        message_text=message_text,
        source_message_id=message_id,
        user_id="user-1",
        direct_signal=direct_signal,
        is_private=is_private,
    )


def _wake(  # noqa: PLR0913
    *,
    user_id: str = "user-1",
    message_text: str = "hello",
    is_tome: bool = False,
    is_private: bool = False,
    is_future_task: bool = False,
    allow_group_initiative: bool = True,
) -> WakeContext:
    return WakeContext(
        bot_self_id="bot-1",
        user_id=user_id,
        message_text=message_text,
        is_tome=is_tome,
        is_private=is_private,
        is_future_task=is_future_task,
        allow_group_initiative=allow_group_initiative,
    )


@pytest.mark.parametrize(
    ("wake", "source", "expected"),
    [
        (
            _wake(user_id="bot-1"),
            _source(),
            RuntimeHardRuleDecision(
                action="drop",
                reason_codes=("bot_self_message",),
                reason_text="Message was sent by the bot itself.",
                evidence={},
                should_observe=False,
                should_reply=False,
            ),
        ),
        (
            _wake(message_text="   "),
            _source(message_text="   "),
            RuntimeHardRuleDecision(
                action="drop",
                reason_codes=("empty_input",),
                reason_text="Message has no usable text content.",
                evidence={},
                should_observe=False,
                should_reply=False,
            ),
        ),
        (
            _wake(allow_group_initiative=False),
            _source(),
            RuntimeHardRuleDecision(
                action="observe",
                reason_codes=("initiative_disabled",),
                reason_text="Ambient group initiative is disabled.",
                evidence={},
                should_observe=True,
                should_reply=False,
            ),
        ),
        (
            _wake(is_tome=True),
            _source(direct_signal=True),
            RuntimeHardRuleDecision(
                action="continue",
                reason_codes=("direct_signal",),
                reason_text="Input directly addresses the bot.",
                evidence={},
                should_observe=True,
                should_reply=True,
            ),
        ),
        (
            _wake(is_private=True),
            _source(is_private=True),
            RuntimeHardRuleDecision(
                action="continue",
                reason_codes=("private_message",),
                reason_text="Private message bypasses ambient initiative budget.",
                evidence={},
                should_observe=True,
                should_reply=True,
            ),
        ),
        (
            _wake(is_future_task=True),
            _source(runtime_mode="future_task"),
            RuntimeHardRuleDecision(
                action="continue",
                reason_codes=("future_task",),
                reason_text="Future task bypasses ambient initiative budget.",
                evidence={},
                should_observe=True,
                should_reply=True,
            ),
        ),
        (
            _wake(),
            _source(),
            RuntimeHardRuleDecision(
                action="continue",
                reason_codes=("ambient_candidate",),
                reason_text="Ambient group input is eligible for later judgment.",
                evidence={},
                should_observe=True,
                should_reply=True,
            ),
        ),
    ],
)
def test_hard_rules_map_existing_wake_signals(
    wake: WakeContext,
    source: RuntimeTurnSource,
    expected: RuntimeHardRuleDecision,
) -> None:
    decision = decide_runtime_hard_rule(wake_context=wake, source=source, now=_now())

    assert decision.action == expected.action
    assert decision.reason_codes == expected.reason_codes
    assert decision.reason_text == expected.reason_text
    assert decision.should_observe is expected.should_observe
    assert decision.should_reply is expected.should_reply
    assert decision.evidence["user_id"] == wake.user_id


def test_hard_rules_drop_duplicate_events() -> None:
    runtime = InMemoryAISessionRuntimeResolver().resolve("session-1", now=_now())
    wake = _wake(is_tome=True)
    source = _source(direct_signal=True)

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
        now=_now(),
    )

    assert first.action == "continue"
    assert duplicate.action == "drop"
    assert duplicate.reason_codes == ("duplicate_event",)
    assert duplicate.should_observe is False
    assert duplicate.should_reply is False
