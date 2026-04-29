from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest  # noqa: TC002

from apeiria.ai.config import AIPluginConfig
from apeiria.ai.model import AIModelBindingTarget
from apeiria.ai.tools import AIToolPolicy
from apeiria.app.ai.pipeline import input_steps
from apeiria.app.ai.pipeline import service as service_module
from apeiria.app.ai.pipeline.input_steps import gather_reply_inputs
from apeiria.app.ai.pipeline.service import (
    AIRuntimeReplyRequest,
    AIRuntimeReplyResult,
    AIRuntimeService,
)
from apeiria.app.ai.reply_strategy import WakeContext
from apeiria.conversation.models import ChatSessionIdentity


def _identity() -> ChatSessionIdentity:
    return ChatSessionIdentity(
        session_id="session-1",
        platform="test",
        bot_id="bot-1",
        scene_type="group",
        scene_id="scene-1",
        subject_id="user-1",
    )


def _request(*, sentiment: object | None = object()) -> AIRuntimeReplyRequest:
    return AIRuntimeReplyRequest(
        identity=_identity(),
        message_text="hello",
        source_message_id="msg-1",
        user_id="user-1",
        sender_id="bot-1",
        runtime_mode="message",
        is_tome=True,
        sentiment=sentiment,  # type: ignore[arg-type]
    )


def _wake() -> WakeContext:
    return WakeContext(
        bot_self_id="bot-1",
        user_id="user-1",
        message_text="hello",
        is_tome=True,
        is_private=False,
        is_future_task=False,
        allow_group_initiative=True,
    )


def test_message_entrypoint_extracts_memory_before_reply_pipeline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    order: list[str] = []

    class ServiceSpy(AIRuntimeService):
        async def _run_reply_pipeline(self, **kwargs: Any) -> AIRuntimeReplyResult:
            order.append("reply_pipeline")
            assert kwargs["request"].sentiment == "sentiment"
            return AIRuntimeReplyResult(reply_text="reply")

    async def ingest_event(*_args: Any, **_kwargs: Any) -> object:
        return _identity(), SimpleNamespace(
            message_id="local-msg-1",
            platform_message_id="platform-msg-1",
        )

    async def store_extracted_memories(*_args: Any, **_kwargs: Any) -> object:
        order.append("memory_extraction")
        return SimpleNamespace(sentiment="sentiment")

    monkeypatch.setattr(service_module, "ensure_app_ai_tools_loaded", lambda: None)
    monkeypatch.setattr(
        service_module,
        "ai_skill_service",
        SimpleNamespace(ensure_initialized=lambda: None),
    )
    monkeypatch.setattr(
        service_module,
        "get_ai_plugin_config",
        AIPluginConfig,
    )
    monkeypatch.setattr(
        service_module,
        "build_wake_context",
        lambda *_args, **_kwargs: _wake(),
    )
    monkeypatch.setattr(
        service_module,
        "evaluate_wake",
        lambda _wake_context: SimpleNamespace(should_process=True),
    )
    monkeypatch.setattr(
        service_module,
        "ai_retention_service",
        SimpleNamespace(maybe_schedule_cleanup=lambda **_kwargs: None),
    )
    monkeypatch.setattr(
        service_module,
        "chat_session_service",
        SimpleNamespace(ingest_event=ingest_event),
    )
    monkeypatch.setattr(
        service_module,
        "store_extracted_memories",
        store_extracted_memories,
    )

    result = asyncio.run(
        ServiceSpy().handle_message(
            SimpleNamespace(self_id="bot-1"),  # type: ignore[arg-type]
            SimpleNamespace(get_user_id=lambda: "user-1", is_tome=lambda: True),
        )
    )

    assert result == "reply"
    assert order == ["memory_extraction", "reply_pipeline"]


def test_reply_input_gathering_preserves_mutating_step_order(  # noqa: C901
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    order: list[str] = []
    relationship_target = object()
    model_target = AIModelBindingTarget(
        conversation_id="session-1",
        group_id="scene-1",
        user_id="user-1",
    )
    tool_policy = AIToolPolicy()

    async def build_context_window(**_kwargs: Any) -> tuple[list[Any], str]:
        order.append("context_window")
        return [], "summary"

    def build_relationship_target(*_args: Any, **_kwargs: Any) -> object:
        order.append("relationship_target")
        return relationship_target

    def build_model_target(*_args: Any, **_kwargs: Any) -> AIModelBindingTarget:
        order.append("model_target")
        return model_target

    async def resolve_tool_policy(*_args: Any, **_kwargs: Any) -> AIToolPolicy:
        order.append("tool_policy")
        return tool_policy

    async def load_persona(*_args: Any, **_kwargs: Any) -> None:
        order.append("persona")

    async def update_relationship(*_args: Any, **_kwargs: Any) -> None:
        order.append("relationship_update")

    async def recall_memories(*_args: Any, **_kwargs: Any) -> list[Any]:
        order.append("memory_recall")
        return []

    async def load_relationship(*_args: Any, **_kwargs: Any) -> str:
        order.append("relationship_context")
        return "friendly"

    async def load_person_profile(*_args: Any, **_kwargs: Any) -> tuple[str, ...]:
        order.append("person_profile")
        return ()

    def list_allowed_tools(_policy: AIToolPolicy) -> list[Any]:
        order.append("allowed_tools")
        return []

    async def resolve_initiative(*_args: Any, **_kwargs: Any) -> float:
        order.append("initiative_bias")
        return 0.0

    monkeypatch.setattr(
        input_steps,
        "build_and_store_context_window",
        build_context_window,
    )
    monkeypatch.setattr(
        input_steps,
        "build_relationship_target",
        build_relationship_target,
    )
    monkeypatch.setattr(input_steps, "build_model_binding_target", build_model_target)
    monkeypatch.setattr(input_steps, "resolve_tool_policy", resolve_tool_policy)
    monkeypatch.setattr(input_steps, "load_persona_bundle", load_persona)
    monkeypatch.setattr(input_steps, "update_relationship_state", update_relationship)
    monkeypatch.setattr(input_steps, "recall_memories", recall_memories)
    monkeypatch.setattr(input_steps, "load_relationship_context", load_relationship)
    monkeypatch.setattr(
        input_steps,
        "load_person_profile_for_prompt",
        load_person_profile,
    )
    monkeypatch.setattr(
        input_steps,
        "ai_tool_service",
        SimpleNamespace(list_allowed_tools=list_allowed_tools),
    )
    monkeypatch.setattr(input_steps, "resolve_initiative_bias", resolve_initiative)

    inputs = asyncio.run(
        gather_reply_inputs(
            _request(sentiment=object()),
            datetime(2026, 4, 29, 12, 0, tzinfo=timezone.utc),
        )
    )

    assert inputs.model_target == model_target
    assert inputs.tool_policy == tool_policy
    assert order == [
        "context_window",
        "relationship_target",
        "model_target",
        "tool_policy",
        "persona",
        "relationship_update",
        "memory_recall",
        "relationship_context",
        "person_profile",
        "allowed_tools",
        "initiative_bias",
    ]
