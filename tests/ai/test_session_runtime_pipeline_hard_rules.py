from __future__ import annotations

import asyncio

import pytest

from apeiria.app.ai.pipeline import service as service_module
from apeiria.app.ai.pipeline.service import (
    AIRuntimeReplyRequest,
    AIRuntimeService,
    AITraceContext,
)
from apeiria.app.ai.reply_strategy import ReplyStrategyDecision, WakeContext
from apeiria.app.ai.session_runtime import map_legacy_skip_to_runtime_decision
from apeiria.conversation.models import ChatSessionIdentity


class _InputGatheredError(RuntimeError):
    """Raised by tests to prove the pipeline reached input gathering."""


def _request(
    *,
    scene_type: str = "group",
    is_tome: bool = False,
    runtime_mode: str = "message",
) -> AIRuntimeReplyRequest:
    return AIRuntimeReplyRequest(
        identity=ChatSessionIdentity(
            session_id="session-1",
            platform="test",
            bot_id="bot-1",
            scene_type=scene_type,  # type: ignore[arg-type]
            scene_id="scene-1",
            subject_id="user-1",
        ),
        message_text="ambient",
        source_message_id="msg-1",
        user_id="user-1",
        sender_id="bot-1",
        runtime_mode=runtime_mode,  # type: ignore[arg-type]
        is_tome=is_tome,
    )


async def _noop_observation_effects(*_args: object, **_kwargs: object) -> None:
    return None


@pytest.mark.parametrize(
    ("runtime_request", "wake_context"),
    [
        (
            _request(),
            WakeContext(
                bot_self_id="bot-1",
                user_id="user-1",
                message_text="ambient",
                is_tome=False,
                is_private=False,
                is_future_task=False,
                allow_group_initiative=True,
            ),
        ),
        (
            _request(is_tome=True),
            WakeContext(
                bot_self_id="bot-1",
                user_id="user-1",
                message_text="ambient",
                is_tome=True,
                is_private=False,
                is_future_task=False,
                allow_group_initiative=True,
            ),
        ),
        (
            _request(scene_type="private"),
            WakeContext(
                bot_self_id="bot-1",
                user_id="user-1",
                message_text="ambient",
                is_tome=False,
                is_private=True,
                is_future_task=False,
                allow_group_initiative=True,
            ),
        ),
        (
            _request(runtime_mode="future_task"),
            WakeContext(
                bot_self_id="bot-1",
                user_id="user-1",
                message_text="ambient",
                is_tome=False,
                is_private=False,
                is_future_task=True,
                allow_group_initiative=True,
            ),
        ),
    ],
)
def test_current_serialized_priority_turn_does_not_self_defer(
    monkeypatch: pytest.MonkeyPatch,
    runtime_request: AIRuntimeReplyRequest,
    wake_context: WakeContext,
) -> None:
    service = AIRuntimeService()

    async def gather_reply_inputs(*_args: object, **_kwargs: object) -> object:
        raise _InputGatheredError

    monkeypatch.setattr(
        service_module,
        "apply_reply_observation_effects",
        _noop_observation_effects,
    )
    monkeypatch.setattr(service_module, "gather_reply_inputs", gather_reply_inputs)

    with pytest.raises(_InputGatheredError):
        asyncio.run(
            service._run_reply_pipeline(
                trace_id="trace-1",
                trace=AITraceContext(kind="test", trigger="unit"),
                request=runtime_request,
                wake_context=wake_context,
            )
        )


def test_observe_hard_rule_skips_input_gather_and_social_judgment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AIRuntimeService()

    async def gather_reply_inputs(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("observe decision should skip input gathering")  # noqa: TRY003

    monkeypatch.setattr(service_module, "gather_reply_inputs", gather_reply_inputs)

    result = asyncio.run(
        service._run_reply_pipeline(
            trace_id="trace-1",
            trace=AITraceContext(kind="test", trigger="unit"),
            request=_request(),
            wake_context=WakeContext(
                bot_self_id="bot-1",
                user_id="user-1",
                message_text="ambient",
                is_tome=False,
                is_private=False,
                is_future_task=False,
                allow_group_initiative=False,
            ),
        )
    )

    assert result is None


@pytest.mark.parametrize(
    ("legacy", "expected_action", "expected_reason"),
    [
        (
            ReplyStrategyDecision(
                action="silent",
                should_speak=False,
                tool_mode="avoid",
                reason_codes=("wait_for_more_context",),
                reason_text="wait",
                evidence={},
                decision_source="llm",
            ),
            "wait",
            ("ambient_merge_window",),
        ),
        (
            ReplyStrategyDecision(
                action="silent",
                should_speak=False,
                tool_mode="avoid",
                reason_codes=("session_busy",),
                reason_text="busy",
                evidence={},
                decision_source="initiative",
            ),
            "defer",
            ("session_busy",),
        ),
        (
            ReplyStrategyDecision(
                action="silent",
                should_speak=False,
                tool_mode="avoid",
                reason_codes=("low_relevance",),
                reason_text="weak ambient context",
                evidence={},
                decision_source="llm",
            ),
            "observe",
            ("ambient_weak_relevance",),
        ),
    ],
)
def test_legacy_no_reply_decisions_map_to_runtime_vocabulary(
    legacy: ReplyStrategyDecision,
    expected_action: str,
    expected_reason: tuple[str, ...],
) -> None:
    mapped = map_legacy_skip_to_runtime_decision(legacy)

    assert mapped.action == expected_action
    assert mapped.reason_codes == expected_reason
    assert mapped.should_reply is False
