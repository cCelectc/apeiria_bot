from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from apeiria.ai.config import AIPluginConfig
from apeiria.ai.model import AIModelBindingTarget
from apeiria.ai.service import AIService
from apeiria.ai.tools import AIToolPolicy, ToolGatewayResult
from apeiria.app.ai.pipeline.input_steps import ReplyInputs
from apeiria.app.ai.pipeline.service import AIRuntimeReplyRequest
from apeiria.app.ai.reply_strategy import ReplyStrategyDecision
from apeiria.conversation.models import ChatSessionIdentity

if TYPE_CHECKING:
    import pytest


class _ModelGatewayStub:
    def __init__(self, selected: Any) -> None:
        self.selected = selected
        self.calls: list[object] = []

    async def select_model(self, *, query: object, target: object | None) -> Any:
        self.calls.append(query)
        assert target is None
        return self.selected


def test_ai_service_status_reports_ready_reply_runtime() -> None:
    selected = SimpleNamespace(
        source=SimpleNamespace(source_id="source-main"),
        profile=SimpleNamespace(profile_id="reply-default", model_id="model-main"),
        resolved_model_name="gpt-main",
    )
    service = AIService(model_gateway=_ModelGatewayStub(selected))

    status = asyncio.run(service.get_status())

    assert status.phase == "runtime_ready"
    assert status.ready is True
    assert "reply generation has a selectable model" in status.summary
    assert "source-main:gpt-main" in status.summary


def test_ai_service_status_reports_degraded_without_reply_model() -> None:
    gateway = _ModelGatewayStub(None)
    service = AIService(model_gateway=gateway)

    status = asyncio.run(service.get_status())

    assert status.phase == "runtime_degraded"
    assert status.ready is False
    assert "Configure or enable a chat model" in status.summary
    assert len(gateway.calls) == 1


def test_reply_preparation_records_no_model_diagnostic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apeiria.app.ai.pipeline import generation_steps

    identity = ChatSessionIdentity(
        session_id="scene-1",
        platform="test",
        bot_id="bot-1",
        scene_type="private",
        scene_id="user-1",
        subject_id=None,
    )
    request = AIRuntimeReplyRequest(
        identity=identity,
        message_text="hello",
        source_message_id="message-1",
        user_id="user-1",
        sender_id="user-1",
        runtime_mode="message",
    )
    inputs = ReplyInputs(
        turns=[],
        conversation_summary=None,
        relationship_target=object(),
        model_target=AIModelBindingTarget(
            conversation_id="scene-1",
            group_id=None,
            user_id="user-1",
        ),
        tool_policy=AIToolPolicy(),
        persona=None,
        recalled_memories=[],
        relationship_context=None,
        person_profile=(),
        allowed_tools=(),
        initiative_bias=0.0,
    )
    social_decision = ReplyStrategyDecision(
        action="reply",
        should_speak=True,
        tool_mode="allow",
        reason_codes=(),
        reason_text="test",
        evidence={},
        decision_source="fallback",
    )
    diagnostics: list[str] = []

    async def prepare_tools(_request: object) -> ToolGatewayResult:
        return ToolGatewayResult(policy_text="", result_lines=(), turns=())

    async def select_model(*, task_class: str, target: object) -> None:
        del task_class, target

    def record_debug(message: str, *args: object) -> None:
        diagnostics.append(message.format(*args) if args else message)

    monkeypatch.setattr(generation_steps, "get_ai_plugin_config", AIPluginConfig)
    monkeypatch.setattr(generation_steps.tool_gateway, "prepare", prepare_tools)
    monkeypatch.setattr(generation_steps, "select_pipeline_model", select_model)
    monkeypatch.setattr(generation_steps.logger, "debug", record_debug)

    result = asyncio.run(
        generation_steps.prepare_generation(
            request=request,
            inputs=inputs,
            social_decision=social_decision,
            current_time=datetime(2026, 4, 27, tzinfo=timezone.utc),
            trace_id="trace-1",
        )
    )

    assert result is None
    assert diagnostics == [
        "AI trace trace-1 skipped reply: no model selected for reply_default "
        "in session scene-1"
    ]
